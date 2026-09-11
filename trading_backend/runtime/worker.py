from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

from firebase_admin import firestore

from trading_backend.backtest import BacktestRunner
from trading_backend.broker.ibkr import IBKRBrokerAdapter, MockBrokerAdapter
from trading_backend.common import US_EASTERN, log, safe_float, utc_now
from trading_backend.data.market_data import MarketDataService
from trading_backend.data.metadata import MetadataRepository
from trading_backend.execution.engine import ExecutionEngine
from trading_backend.logging.audit import AuditLogger
from trading_backend.models import BacktestRequest, PositionPlan, Proposal, ResearchRequest, RuntimeConfig
from trading_backend.positions.monitor import PositionMonitor
from trading_backend.proposals.manager import ProposalManager
from trading_backend.research import ResearchLoopEngine
from trading_backend.risk.engine import RiskEngine
from trading_backend.strategy.v12_pullback import V12PullbackStrategy


def next_trading_day(value: date) -> date:
    current = value + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


class RuntimeWorker:
    def __init__(self, db: firestore.Client, config: RuntimeConfig) -> None:
        self.db = db
        self.config = config
        self.broker = MockBrokerAdapter(config.runtime_id) if config.use_mock_broker else IBKRBrokerAdapter(config.runtime_id)
        self.audit = AuditLogger(config)
        self.metadata = MetadataRepository(config)
        self.market_data = MarketDataService(self.broker)
        self.strategy = V12PullbackStrategy()
        self.risk_engine = RiskEngine()
        self.proposals = ProposalManager()
        self.execution = ExecutionEngine(self.broker)
        self.position_monitor = PositionMonitor()
        self.backtests = BacktestRunner(self.broker, self.metadata, self.strategy, self.risk_engine, config)
        self.service_state = "Disconnected"
        self.bot_state = "Disconnected"
        self.connection_state = "Disconnected"
        self.desired_connection = False
        self.emergency_stop_active = False
        self.flatten_all_requested = False
        self.advisor_mode_enabled = False
        self.execution_mode = "Advisor OFF"
        self.scan_status = "idle"
        self.market_session_state = "closed"
        self.last_control_issued_at = None
        self.last_logged_connection = None
        self.active_proposal: Proposal = self.proposals.empty(self.execution_mode, "No active proposal.")
        self.daily_bars_cache: dict[str, Any] = {}
        self.last_daily_refresh_at: datetime | None = None
        self.last_scan_at: datetime | None = None
        self.last_signal_at: datetime | None = None
        self.last_reconnect_at: datetime | None = None
        self.last_error: str | None = None
        self.last_proposal_validation_at: datetime | None = None
        self.write_counts: Counter[str] = Counter()
        self.last_status_payload: dict[str, Any] | None = None
        self.last_finance_payload: dict[str, Any] | None = None
        self.last_risk_payload: dict[str, Any] | None = None
        self.last_proposal_payload: dict[str, Any] | None = None
        self.last_positions_signature: str | None = None
        self.last_orders_signature: str | None = None
        self.last_trade_signature: str | None = None
        self.last_heartbeat_write_at: datetime | None = None
        self.runtime_state = {
            "daily_lock": False,
            "weekly_lock": False,
            "kill_switch_active": False,
            "new_trades_today": 0,
            "losses_today": 0,
            "weekly_drawdown_pct": 0.0,
            "portfolio_risk_pct": 0.0,
            "cooldowns": {},
        }
        self.managed_positions: dict[str, PositionPlan] = {}
        self.pending_entry_symbol: str | None = None
        self.backtest_status = "idle"
        self.backtest_progress = "Idle"
        self.last_backtest_at: datetime | None = None
        self.last_backtest_run_id: str | None = None
        self.research_status = "idle"
        self.research_progress = "Idle"
        self.research_last_loop_id: str | None = None
        self.research_completed_loops = 0
        self.research_max_loops = 50
        self.research_stop_requested = False
        self.research_target_met = False
        self.research_thread: threading.Thread | None = None
        research_dir = self.audit.db_path.parent.parent / "research"
        self.research = ResearchLoopEngine(self.config.runtime_id, research_dir)
        self.hydrate_runtime_state()

    def runtime_collection(self, name: str):
        return self.db.collection("runtimes").document(self.config.runtime_id).collection(name)

    def runtime_doc(self, collection_name: str, doc_id: str):
        return self.runtime_collection(collection_name).document(doc_id)

    def proposal_doc(self):
        return self.runtime_doc("proposal", "current")

    def count_write(self, bucket: str, amount: int = 1) -> None:
        self.write_counts[bucket] += amount

    def flush_write_counts(self) -> None:
        if not self.write_counts:
            return
        summary = ", ".join(f"{key}={value}" for key, value in sorted(self.write_counts.items()))
        log(f"{self.config.runtime_id}: firestore counters -> {summary}")
        self.write_counts.clear()

    def hydrate_runtime_state(self) -> None:
        persisted = self.audit.load_state("runtime_state")
        if persisted:
            self.runtime_state.update(persisted.get("runtime_state", {}))
            for symbol, row in persisted.get("managed_positions", {}).items():
                self.managed_positions[symbol] = PositionPlan(**row)
            self.last_daily_refresh_at = datetime.fromisoformat(persisted["last_daily_refresh_at"]) if persisted.get("last_daily_refresh_at") else None
            self.backtest_status = persisted.get("backtest_status", self.backtest_status)
            self.backtest_progress = persisted.get("backtest_progress", self.backtest_progress)
            self.last_backtest_at = datetime.fromisoformat(persisted["last_backtest_at"]) if persisted.get("last_backtest_at") else None
            self.last_backtest_run_id = persisted.get("last_backtest_run_id")
            self.research_status = persisted.get("research_status", self.research_status)
            self.research_progress = persisted.get("research_progress", self.research_progress)
            self.research_last_loop_id = persisted.get("research_last_loop_id")
            self.research_completed_loops = int(persisted.get("research_completed_loops", self.research_completed_loops))
            self.research_max_loops = int(persisted.get("research_max_loops", self.research_max_loops))
            self.research_target_met = bool(persisted.get("research_target_met", self.research_target_met))
        try:
            status_snap = self.runtime_doc("system", "status").get()
            if status_snap.exists:
                status = status_snap.to_dict() or {}
                self.desired_connection = bool(status.get("desired_connection", False) and status.get("ibkr_connected", False))
                self.emergency_stop_active = bool(status.get("emergency_stop_active", False))
                self.advisor_mode_enabled = bool(status.get("advisor_mode_enabled", False))
                self.execution_mode = "Advisor ON" if self.advisor_mode_enabled else "Advisor OFF"
                self.bot_state = status.get("bot_state") or "Disconnected"
                self.connection_state = status.get("connection_state") or "Disconnected"
                self.service_state = status.get("service_state") or self.bot_state
        except Exception as exc:
            log(f"{self.config.runtime_id}: hydrate status skipped: {exc}")
        try:
            proposal_snap = self.proposal_doc().get()
            if proposal_snap.exists:
                row = proposal_snap.to_dict() or {}
                self.active_proposal = Proposal(
                    proposal_id=row.get("proposal_id"),
                    symbol=row.get("symbol"),
                    side=row.get("side"),
                    quantity=int(row.get("quantity") or 0),
                    order_type=row.get("order_type"),
                    entry_trigger_price=row.get("entry_trigger_price"),
                    stop_loss=row.get("stop_loss"),
                    take_profit=row.get("take_profit"),
                    risk_reward=row.get("risk_reward"),
                    risk_per_share=row.get("risk_per_share"),
                    score=row.get("score"),
                    confidence_score=row.get("confidence_score"),
                    sector=row.get("sector"),
                    strategy_tag=row.get("strategy_tag") or "v1.2_pullback_long",
                    rationale=row.get("rationale") or "No active proposal.",
                    proposal_status=row.get("proposal_status") or "None",
                    approval_required=bool(row.get("approval_required", True)),
                    mode=row.get("mode") or self.execution_mode,
                    created_at=row.get("created_at") or utc_now(),
                    last_validated_at=row.get("last_validated_at") or utc_now(),
                    expires_at=row.get("expires_at"),
                    valid_for_date=date.fromisoformat(row["valid_for_date"]) if row.get("valid_for_date") else None,
                    invalid_reason=row.get("invalid_reason"),
                    entry_order_id=row.get("entry_order_id"),
                    validation_snapshot=row.get("validation_snapshot") or {},
                )
        except Exception as exc:
            log(f"{self.config.runtime_id}: hydrate proposal skipped: {exc}")
        try:
            control_snap = self.runtime_doc("control", "current").get()
            if control_snap.exists:
                control = control_snap.to_dict() or {}
                if control.get("acknowledged_at") and control.get("issued_at"):
                    self.last_control_issued_at = control["issued_at"]
        except Exception as exc:
            log(f"{self.config.runtime_id}: hydrate control skipped: {exc}")

    def persist_runtime_state(self) -> None:
        self.audit.save_state(
            "runtime_state",
            {
                "runtime_state": self.runtime_state,
                "last_daily_refresh_at": self.last_daily_refresh_at.isoformat() if self.last_daily_refresh_at else None,
                "managed_positions": {symbol: asdict(plan) for symbol, plan in self.managed_positions.items()},
                "backtest_status": self.backtest_status,
                "backtest_progress": self.backtest_progress,
                "last_backtest_at": self.last_backtest_at.isoformat() if self.last_backtest_at else None,
                "last_backtest_run_id": self.last_backtest_run_id,
                "research_status": self.research_status,
                "research_progress": self.research_progress,
                "research_last_loop_id": self.research_last_loop_id,
                "research_completed_loops": self.research_completed_loops,
                "research_max_loops": self.research_max_loops,
                "research_target_met": self.research_target_met,
            },
        )

    def log_event(self, level: str, message: str, detail: str | None = None, source: str = "backend", symbol: str | None = None, order_id: str | None = None, trade_id: str | None = None) -> None:
        category = source if source in {"order", "strategy", "risk", "emergency"} else ("error" if level == "error" else "info")
        detail_payload = {"detail": detail} if detail else {}
        self.audit.log_event(self.config.runtime_id, category, source, level, message, detail_payload, symbol=symbol, order_id=order_id, trade_id=trade_id)
        try:
            self.runtime_collection("logs").add(
                {
                    "category": category,
                    "level": level,
                    "message": message,
                    "detail": detail,
                    "source": source,
                    "symbol": symbol,
                    "order_id": order_id,
                    "trade_id": trade_id,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                }
            )
            self.count_write("logs_add")
        except Exception as exc:
            log(f"{self.config.runtime_id}: log write skipped: {exc}")

    def log_risk_check(self, symbol: str | None, decision) -> None:
        self.audit.log_risk_check(self.config.runtime_id, symbol, decision.passed, decision.reason, decision.checks)

    def market_logic_now(self) -> datetime:
        return utc_now().astimezone(US_EASTERN)

    def set_advisor_mode(self, enabled: bool) -> None:
        self.advisor_mode_enabled = enabled
        self.execution_mode = "Advisor ON" if enabled else "Advisor OFF"

    def process_control(self) -> None:
        snap = self.runtime_doc("control", "current").get()
        if not snap.exists:
            return
        data = snap.to_dict() or {}
        action = (data.get("action") or "").lower()
        issued_at = data.get("issued_at")
        if not action or issued_at is None:
            return
        if self.last_control_issued_at and issued_at == self.last_control_issued_at:
            return
        if action == "connect":
            self.desired_connection = True
            self.set_advisor_mode(False)
            self.ensure_connected(force=True)
            self.service_state = "Ready"
            self.bot_state = "Ready"
        elif action == "disconnect":
            self.desired_connection = False
            self.broker.disconnect()
            self.connection_state = "Disconnected"
            self.service_state = "Disconnected"
            self.bot_state = "Disconnected"
        elif action in {"set_advisor_mode_on", "set_mode_agent"}:
            if not self.emergency_stop_active:
                self.set_advisor_mode(True)
        elif action in {"set_advisor_mode_off", "set_mode_advisor"}:
            self.set_advisor_mode(False)
        elif action == "pause":
            if not self.emergency_stop_active:
                self.bot_state = "Paused"
                self.service_state = "Paused"
        elif action == "resume":
            if not self.emergency_stop_active:
                self.bot_state = "Ready"
                self.service_state = "Ready"
                if self.desired_connection:
                    self.ensure_connected(force=True)
        elif action == "approve_proposal":
            self.approve_active_proposal()
        elif action == "reject_proposal":
            self.reject_active_proposal()
        elif action == "clear_emergency":
            self.clear_emergency()
        elif action == "flatten_all":
            self.execute_flatten_all()
        elif action == "run_backtest":
            raw_symbols = str(data.get("symbols") or "").strip()
            parsed_symbols = [symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()]
            request = BacktestRequest(
                lookback_days=max(120, int(data.get("lookback_days") or self.config.backtest_lookback_days)),
                capital_sek=float(data.get("capital_sek") or self.config.account_size_sek),
                strategy_key=str(data.get("strategy_key") or "v1.2_pullback_long"),
                symbols=parsed_symbols,
                data_source=str(data.get("data_source") or "ibkr").lower(),
            )
            self.execute_backtest(request)
        elif action == "clear_backtests":
            self.clear_backtests()
        elif action == "start_research_loop":
            raw_symbols = str(data.get("symbols") or "").strip()
            parsed_symbols = [symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()]
            request = ResearchRequest(
                seed_strategy_key=str(data.get("strategy_key") or "v1.2_pullback_long"),
                lookback_days=max(120, int(data.get("lookback_days") or self.config.backtest_lookback_days)),
                capital_sek=float(data.get("capital_sek") or self.config.account_size_sek),
                symbols=parsed_symbols,
                data_source=str(data.get("data_source") or "alpaca").lower(),
                max_loops=max(1, min(50, int(data.get("max_loops") or 50))),
            )
            self.start_research_loop(request)
        elif action == "stop_research_loop":
            self.stop_research_loop()
        elif action == "stop":
            self.execute_emergency_halt()
        else:
            self.log_event("warn", f"Unknown control action ignored: {action}", source="control")
            self.last_control_issued_at = issued_at
            return
        self.runtime_doc("control", "current").set(
            {"action": action, "issued_at": issued_at, "acknowledged_at": firestore.SERVER_TIMESTAMP, "processed_by": "trading_backend/service.py"},
            merge=True,
        )
        self.count_write("control_ack")
        self.last_control_issued_at = issued_at
        self.log_event("info", f"{self.config.label} runtime acknowledged: {action}", source="control")

    def ensure_connected(self, force: bool = False) -> None:
        if self.broker.get_snapshot().connected and not force:
            return
        self.connection_state = "Connecting" if self.connection_state in {"Disconnected", "Faulted"} else "Reconnecting"
        try:
            self.broker.connect()
            self.connection_state = "Connected"
            self.last_reconnect_at = utc_now()
            self.set_advisor_mode(False)
            if self.bot_state not in {"Paused", "Emergency Halt"}:
                self.bot_state = "Ready"
                self.service_state = "Ready"
        except Exception as exc:
            self.connection_state = "Faulted"
            self.service_state = "Faulted"
            self.bot_state = "Faulted"
            self.last_error = str(exc)
            self.log_event("error", f"{self.config.label} runtime connect failed.", detail=str(exc), source="broker")

    def clear_emergency(self) -> None:
        self.emergency_stop_active = False
        self.flatten_all_requested = False
        self.desired_connection = True
        self.set_advisor_mode(False)
        self.active_proposal = self.proposals.empty(self.execution_mode, "Emergency cleared. Ready to resume in Advisor Mode OFF.")
        self.service_state = "Ready"
        self.bot_state = "Ready"
        self.ensure_connected(force=True)

    def execute_emergency_halt(self) -> None:
        log(f"{self.config.runtime_id}: emergency halt requested.")
        self.emergency_stop_active = True
        self.flatten_all_requested = False
        self.set_advisor_mode(False)
        self.service_state = "EmergencyHalt"
        self.bot_state = "Emergency Halt"
        self.desired_connection = True
        self.ensure_connected(force=True)
        self.active_proposal = self.proposals.empty(self.execution_mode, "Emergency halt triggered.")
        cancel_result = self.broker.cancel_entry_orders()
        self.log_event("error", f"{self.config.label} emergency halt executed.", detail=f"Cancelled {cancel_result.get('cancelled_orders', 0)} working entry orders.", source="emergency")

    def execute_flatten_all(self) -> None:
        log(f"{self.config.runtime_id}: flatten all requested.")
        self.emergency_stop_active = True
        self.flatten_all_requested = True
        self.set_advisor_mode(False)
        self.service_state = "EmergencyHalt"
        self.bot_state = "Emergency Halt"
        self.desired_connection = True
        self.ensure_connected(force=True)
        cancel_result = self.broker.cancel_all_orders()
        close_result = self.broker.close_all_positions()
        self.log_event(
            "error",
            f"{self.config.label} flatten all executed.",
            detail=f"Cancelled {cancel_result.get('cancelled_orders', 0)} orders; submitted {close_result.get('submitted_close_orders', 0)} close orders.",
            source="emergency",
        )

    def execute_backtest(self, request: BacktestRequest) -> None:
        self.backtest_status = "running"
        self.backtest_progress = f"Running {request.strategy_key} backtest over {request.lookback_days} days using {request.data_source.upper()} data."
        self.log_event("info", f"{self.config.label} backtest started.", detail=f"Strategy={request.strategy_key} | Lookback={request.lookback_days} days | Source={request.data_source.upper()}", source="strategy")
        try:
            if str(request.data_source or "ibkr").lower() == "ibkr":
                self.ensure_connected(force=True)
            result = self.backtests.run(request, progress_cb=self.report_backtest_progress)
            self.save_backtest_result(result)
            self.backtest_status = "completed"
            self.backtest_progress = f"Completed {result.trades} trades | Return {result.return_pct:.2f}% | Sharpe {result.sharpe:.2f}"
            self.last_backtest_at = utc_now()
            self.last_backtest_run_id = result.run_id
            self.log_event("info", f"{self.config.label} backtest completed.", detail=self.backtest_progress, source="strategy")
        except Exception as exc:
            self.backtest_status = "failed"
            self.backtest_progress = f"Backtest failed: {exc}"
            self.last_error = str(exc)
            self.log_event("error", f"{self.config.label} backtest failed.", detail=str(exc), source="strategy")

    def save_backtest_result(self, result) -> None:
        payload = result.to_firestore()
        self.runtime_collection("backtests").document(result.run_id).set({**payload, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        self.count_write("backtests_set")
        self.audit.save_backtest_run({**payload, "timestamp": result.timestamp.isoformat()})

    def report_backtest_progress(self, message: str) -> None:
        self.backtest_progress = message
        log(f"{self.config.runtime_id}: backtest progress -> {message}")
        try:
            self.runtime_doc("system", "status").set(
                {
                    "backtest_status": self.backtest_status,
                    "backtest_progress": self.backtest_progress,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            self.count_write("system_status")
        except Exception as exc:
            log(f"{self.config.runtime_id}: backtest progress publish skipped: {exc}")

    def clear_backtests(self) -> None:
        docs = list(self.runtime_collection("backtests").stream())
        if docs:
            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
                self.count_write("backtests_delete")
            batch.commit()
        self.audit.clear_backtest_runs(self.config.runtime_id)
        self.backtest_status = "idle"
        self.backtest_progress = "Cleared previous backtest runs."
        self.last_backtest_at = None
        self.last_backtest_run_id = None
        self.log_event("info", f"{self.config.label} backtest runs cleared.", source="strategy")

    def start_research_loop(self, request: ResearchRequest) -> None:
        if self.research_thread and self.research_thread.is_alive():
            self.research_progress = "Research loop already running."
            return
        self.research_stop_requested = False
        self.research_target_met = False
        self.research_completed_loops = 0
        self.research_max_loops = request.max_loops
        self.research_last_loop_id = None
        self.research_status = "running"
        self.research_progress = (
            f"Starting research loop from {request.seed_strategy_key} "
            f"using {request.data_source.upper()} data. Loop 0/{request.max_loops}."
        )
        self.log_event(
            "info",
            f"{self.config.label} research loop started.",
            detail=f"Seed={request.seed_strategy_key} | Lookback={request.lookback_days} | Source={request.data_source.upper()} | MaxLoops={request.max_loops}",
            source="strategy",
        )
        self.report_research_progress(self.research_progress)

        def worker() -> None:
            try:
                if str(request.data_source or "alpaca").lower() == "ibkr":
                    self.ensure_connected(force=True)
                summary = self.research.run(
                    request=request,
                    run_backtest=self.backtests.run,
                    publish_loop=self.publish_research_loop_result,
                    stop_requested=lambda: self.research_stop_requested,
                    progress_cb=self.report_research_progress,
                )
                self.research_completed_loops = int(summary.get("completed_loops") or 0)
                self.research_target_met = bool(summary.get("target_met", False))
                self.research_last_loop_id = summary.get("last_loop_id")
                if self.research_stop_requested:
                    self.research_status = "stopped"
                    self.research_progress = f"Research loop stopped after loop {self.research_completed_loops}/{self.research_max_loops}."
                elif self.research_target_met:
                    self.research_status = "completed"
                    self.research_progress = f"Target met at {self.research_last_loop_id} after loop {self.research_completed_loops}/{self.research_max_loops}."
                else:
                    self.research_status = "completed"
                    self.research_progress = f"Completed {self.research_completed_loops}/{self.research_max_loops} loops without meeting all targets."
                self.log_event("info", f"{self.config.label} research loop finished.", detail=self.research_progress, source="strategy")
            except Exception as exc:
                self.research_status = "failed"
                self.research_progress = f"Research loop failed: {exc}"
                self.last_error = str(exc)
                self.log_event("error", f"{self.config.label} research loop failed.", detail=str(exc), source="strategy")
            finally:
                self.report_research_progress(self.research_progress)
                self.persist_runtime_state()

        self.research_thread = threading.Thread(target=worker, name=f"{self.config.runtime_id}-research", daemon=True)
        self.research_thread.start()

    def stop_research_loop(self) -> None:
        self.research_stop_requested = True
        if self.research_status == "running":
            self.research_status = "stopping"
            self.research_progress = "Stop requested. Waiting for the current loop to finish cleanly."
            self.report_research_progress(self.research_progress)
        self.log_event("warn", f"{self.config.label} research loop stop requested.", source="strategy")

    def publish_research_loop_result(self, record, result) -> None:
        result.meta = result.meta or {}
        result.meta["research_loop"] = True
        result.meta["research_loop_id"] = record.loop_id
        result.meta["research_family_id"] = record.family_id
        result.meta["research_result"] = record.result
        result.meta["research_score"] = record.strategy_score
        result.meta["research_previous_score"] = record.previous_score
        result.meta["research_annual_return_pct"] = record.annual_return_pct
        result.meta["research_rca_needed"] = record.rca_needed
        result.meta["research_rca_result"] = record.rca_result
        result.meta["research_fix"] = record.fix
        result.meta["research_decision"] = record.decision
        result.meta["research_new_strategy_id"] = record.new_strategy_id
        result.meta["research_target_met"] = record.target_met
        result.notes = f"{record.loop_id} | {record.result} | Score {record.strategy_score} | {record.decision}"
        self.save_backtest_result(result)
        self.audit.save_research_loop(self.config.runtime_id, {**record.to_dict(), "timestamp": record.timestamp.isoformat()})
        self.research_completed_loops += 1
        self.research_last_loop_id = record.loop_id
        self.last_backtest_at = result.timestamp
        self.last_backtest_run_id = result.run_id
        self.report_research_progress(
            f"Loop {self.research_completed_loops}/{self.research_max_loops} · {record.loop_id}: {record.result} | Score {record.strategy_score} | "
            f"Annual {record.annual_return_pct:.2f}% | DD {record.max_drawdown_pct:.2f}% | Sharpe {record.sharpe:.2f}"
        )

    def report_research_progress(self, message: str) -> None:
        self.research_progress = message
        log(f"{self.config.runtime_id}: research progress -> {message}")
        try:
            self.runtime_doc("system", "status").set(
                {
                    "research_status": self.research_status,
                    "research_progress": self.research_progress,
                    "research_last_loop_id": self.research_last_loop_id,
                    "research_completed_loops": self.research_completed_loops,
                    "research_max_loops": self.research_max_loops,
                    "research_stop_requested": self.research_stop_requested,
                    "research_target_met": self.research_target_met,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            self.count_write("system_status")
        except Exception as exc:
            log(f"{self.config.runtime_id}: research progress publish skipped: {exc}")

    def refresh_daily_data(self) -> None:
        self.scan_status = "running"
        self.service_state = "DailyPrep"
        self.bot_state = "DailyPrep"
        self.log_event("info", f"{self.config.label} daily signal preparation started.", source="strategy")
        bars_cache: dict[str, Any] = {}
        for item in self.metadata.active_items():
            try:
                bars_cache[item.symbol] = self.market_data.fetch_daily_bars(item.symbol)
            except Exception as exc:
                self.log_event("error", f"Daily bars refresh failed for {item.symbol}.", detail=str(exc), source="strategy", symbol=item.symbol)
        self.daily_bars_cache = bars_cache
        self.last_daily_refresh_at = utc_now()
        self.last_scan_at = utc_now()
        self.scan_status = "idle"
        self.log_event("info", f"{self.config.label} daily signal preparation completed.", detail=f"Loaded {len(self.daily_bars_cache)} symbols.", source="strategy")

    def evaluate_daily_candidates(self, snapshot) -> None:
        self.service_state = "ScanningDaily"
        self.bot_state = "ScanningDaily"
        self.scan_status = "running"
        today = self.market_data.trading_day()
        fx_usdsek = float(11.0)
        best = None
        best_item = None
        best_decision = None
        for item in self.metadata.active_items():
            if self.market_data.within_earnings_blackout(item, today):
                self.log_event("info", f"{item.symbol} rejected: earnings blackout window.", source="strategy", symbol=item.symbol)
                continue
            cooldowns = self.runtime_state.get("cooldowns", {})
            if cooldowns.get(item.symbol) == today.isoformat():
                continue
            bars = self.daily_bars_cache.get(item.symbol) or []
            candidate, reason = self.strategy.evaluate(item, bars)
            if not candidate:
                self.log_event("info", f"{item.symbol} rejected: {reason}", source="strategy", symbol=item.symbol)
                continue
            candidate.valid_for_date = next_trading_day(candidate.setup_date)
            quote = self.market_data.quote_snapshot(item.symbol)
            quote_ok, quote_reason = self.market_data.validate_quote(quote, item)
            if not quote_ok:
                self.log_event("info", f"{item.symbol} rejected: {quote_reason}", source="strategy", symbol=item.symbol)
                continue
            decision = self.risk_engine.evaluate_entry(candidate, snapshot.account, snapshot.positions, self.runtime_state, fx_usdsek, item)
            self.log_risk_check(item.symbol, decision)
            if not decision.passed:
                self.log_event("info", f"{item.symbol} rejected by risk: {decision.reason}", source="risk", symbol=item.symbol)
                continue
            if best is None or candidate.score > best.score:
                best = candidate
                best_item = item
                best_decision = decision
        if best and best_item and best_decision:
            status = "Active"
            if self.active_proposal.symbol == best.symbol and self.active_proposal.proposal_status in {"Active", "Approved", "Refreshed"}:
                status = "Refreshed"
            self.active_proposal = self.proposals.from_candidate(best, best_decision, self.execution_mode, status=status)
            self.last_signal_at = utc_now()
            self.log_event("info", f"Proposal {status.lower()} for {best.symbol}.", detail=best.rationale, source="strategy", symbol=best.symbol)
        else:
            self.active_proposal = self.proposals.empty(self.execution_mode, "No valid daily setup after scan.")
        self.scan_status = "idle"
        self.service_state = "ProposalActive" if self.active_proposal.symbol else "Ready"
        self.bot_state = "AwaitingApproval" if self.active_proposal.symbol and not self.advisor_mode_enabled else self.service_state

    def revalidate_active_proposal(self, snapshot) -> None:
        proposal = self.active_proposal
        if not proposal.symbol or proposal.proposal_status in {"None", "Rejected", "Submitted", "Expired", "Invalidated"}:
            return
        if self.last_proposal_validation_at and (utc_now() - self.last_proposal_validation_at).total_seconds() < 60:
            return
        self.last_proposal_validation_at = utc_now()
        today = self.market_data.trading_day()
        if proposal.valid_for_date and today > proposal.valid_for_date:
            self.active_proposal = self.proposals.invalidate(proposal, "Proposal day has passed.", status="Expired")
            self.runtime_state.setdefault("cooldowns", {})[proposal.symbol] = today.isoformat()
            return
        if self.runtime_state.get("daily_lock") or self.runtime_state.get("weekly_lock") or self.runtime_state.get("kill_switch_active"):
            self.active_proposal = self.proposals.invalidate(proposal, "Risk lock triggered.", status="Invalidated")
            return
        if any((pos.get("sector") or "") == proposal.sector for pos in snapshot.positions if safe_float(pos.get("quantity")) != 0):
            self.active_proposal = self.proposals.invalidate(proposal, "Sector is now occupied.", status="Invalidated")
            return
        if proposal.valid_for_date and today == proposal.valid_for_date:
            quote = self.market_data.quote_snapshot(proposal.symbol)
            last = safe_float(quote.get("last"))
            if not self.market_data.is_after_entry_time() and last >= safe_float(proposal.entry_trigger_price):
                self.active_proposal = self.proposals.invalidate(proposal, "Entry breached before 10:15 ET.", status="Invalidated")
                self.runtime_state.setdefault("cooldowns", {})[proposal.symbol] = today.isoformat()
                return
        proposal.last_validated_at = utc_now()
        proposal.expires_at = utc_now() + timedelta(seconds=60)

    def approve_active_proposal(self) -> None:
        if self.active_proposal.proposal_status not in {"Active", "Refreshed"}:
            return
        self.active_proposal.proposal_status = "Approved"
        self.active_proposal.last_validated_at = utc_now()
        self.log_event("info", f"Proposal approved for {self.active_proposal.symbol}.", source="control", symbol=self.active_proposal.symbol)

    def reject_active_proposal(self) -> None:
        symbol = self.active_proposal.symbol
        if symbol:
            self.runtime_state.setdefault("cooldowns", {})[symbol] = self.market_data.trading_day().isoformat()
        self.active_proposal = self.proposals.empty(self.execution_mode, "User rejected the active proposal.")

    def maybe_submit_planned_entry(self, snapshot) -> None:
        proposal = self.active_proposal
        if not proposal.symbol or proposal.proposal_status not in {"Approved", "Active", "Refreshed"}:
            return
        if not self.market_data.is_market_open() or not self.market_data.is_after_entry_time():
            return
        today = self.market_data.trading_day()
        if proposal.valid_for_date and today != proposal.valid_for_date:
            return
        if not self.advisor_mode_enabled and proposal.proposal_status != "Approved":
            return
        entry, plan = self.execution.submit_entry(proposal)
        proposal.proposal_status = "Submitted"
        proposal.entry_order_id = entry.get("order_id")
        self.pending_entry_symbol = proposal.symbol
        self.managed_positions[proposal.symbol] = plan
        self.service_state = "SubmittingEntry"
        self.bot_state = "SubmittingEntry"
        self.log_event("info", f"Entry submitted for {proposal.symbol}.", detail=f"Buy stop {proposal.entry_trigger_price}", source="order", symbol=proposal.symbol, order_id=entry.get("order_id"))

    def refresh_runtime_locks(self, snapshot) -> None:
        total_drawdown = safe_float(snapshot.account.get("max_drawdown_pct"))
        self.runtime_state["daily_lock"] = bool(self.runtime_state.get("losses_today", 0) >= 2)
        self.runtime_state["weekly_lock"] = bool(self.runtime_state.get("weekly_drawdown_pct", 0.0) >= 3.0)
        self.runtime_state["kill_switch_active"] = bool(total_drawdown >= 8.0)
        portfolio_risk = 0.0
        for symbol, plan in self.managed_positions.items():
            position = next((p for p in snapshot.positions if p.get("symbol") == symbol), None)
            if position:
                portfolio_risk += max(0.0, (safe_float(position.get("quantity")) * abs(plan.entry_price - plan.stop_price)) / max(safe_float(snapshot.account.get("net_liquidation")), 1.0) * 100.0)
        self.runtime_state["portfolio_risk_pct"] = round(portfolio_risk, 4)

    def monitor_positions(self, snapshot) -> None:
        if not self.managed_positions:
            return
        for symbol, plan in list(self.managed_positions.items()):
            position_row = next((row for row in snapshot.positions if row.get("symbol") == symbol and safe_float(row.get("quantity")) > 0), None)
            if position_row and not plan.stop_order_id:
                stop = self.execution.place_initial_stop(plan)
                self.log_event("info", f"Protective stop submitted for {symbol}.", detail=f"Stop {plan.stop_price}", source="order", symbol=symbol, order_id=stop.get("order_id"))
            if not position_row and self.active_proposal.entry_order_id == plan.entry_order_id:
                live_order = next((row for row in snapshot.orders if row.get("order_id") == plan.entry_order_id), None)
                if not live_order or str(live_order.get("status", "")).upper() in {"CANCELLED", "REJECTED"}:
                    self.active_proposal = self.proposals.empty(self.execution_mode, f"Entry for {symbol} is no longer active.")
                    self.runtime_state.setdefault("cooldowns", {})[symbol] = self.market_data.trading_day().isoformat()
                    self.managed_positions.pop(symbol, None)
                continue
            if not position_row:
                continue
            quote = self.market_data.quote_snapshot(symbol)
            bars = self.daily_bars_cache.get(symbol) or []
            action, reason = self.position_monitor.evaluate(plan, position_row, quote, bars)
            if action == "partial_1r":
                qty = max(1, plan.quantity // 2)
                self.execution.flatten_position(symbol, qty)
                plan.partial_taken = True
                self.log_event("info", f"Partial exit submitted for {symbol}.", detail=reason, source="order", symbol=symbol)
            elif action in {"full_2r", "ema_exit", "stop"}:
                qty = int(safe_float(position_row.get("quantity")))
                if qty > 0:
                    self.execution.flatten_position(symbol, qty)
                    self.log_event("info", f"Exit submitted for {symbol}.", detail=reason, source="order", symbol=symbol)
                    self.managed_positions.pop(symbol, None)
                    self.service_state = "MonitoringPositions"
                    self.bot_state = "MonitoringPositions"

    def update_runtime_state(self, snapshot) -> None:
        now = self.market_logic_now()
        self.market_session_state = "open" if self.market_data.is_market_open() else ("preopen" if (now.hour, now.minute) < (9, 30) else "postclose")
        if snapshot.connected:
            self.connection_state = "Connected"
        elif self.desired_connection:
            self.connection_state = "Reconnecting"
        else:
            self.connection_state = "Disconnected"
        if self.emergency_stop_active:
            self.service_state = "EmergencyHalt"
            self.bot_state = "Emergency Halt"
            return
        if self.bot_state == "Paused":
            self.service_state = "Paused"
            return
        if not snapshot.connected:
            self.service_state = "Disconnected"
            self.bot_state = "Disconnected"
            return
        if self.managed_positions:
            self.service_state = "MonitoringPositions"
            self.bot_state = "MonitoringPositions"
        elif self.active_proposal.symbol:
            self.service_state = "ProposalActive"
            self.bot_state = "AwaitingApproval" if not self.advisor_mode_enabled else "Ready"
        else:
            self.service_state = "Ready"
            self.bot_state = "Ready"

    def publish(self) -> None:
        if self.desired_connection and not self.broker.get_snapshot().connected and not self.emergency_stop_active:
            self.ensure_connected()
        snapshot = self.broker.get_snapshot()
        self.refresh_runtime_locks(snapshot)
        self.update_runtime_state(snapshot)
        if snapshot.connected and self.market_data.daily_refresh_due(self.last_daily_refresh_at):
            self.refresh_daily_data()
            self.evaluate_daily_candidates(snapshot)
            snapshot = self.broker.get_snapshot()
            self.refresh_runtime_locks(snapshot)
            self.update_runtime_state(snapshot)
        if snapshot.connected and not self.emergency_stop_active:
            if self.bot_state != "Paused":
                self.revalidate_active_proposal(snapshot)
                self.maybe_submit_planned_entry(snapshot)
            self.monitor_positions(snapshot)
        self.publish_snapshot(snapshot)
        self.publish_proposal()
        self.track_connection_transition(snapshot.connected)
        self.persist_runtime_state()

    def publish_snapshot(self, snapshot) -> None:
        account = snapshot.account
        status_payload = {
            "runtime_id": self.config.runtime_id,
            "runtime_label": self.config.label,
            "service_state": self.service_state,
            "bot_state": self.bot_state,
            "connection_state": self.connection_state,
            "desired_connection": self.desired_connection,
            "emergency_stop_active": self.emergency_stop_active,
            "flatten_all_requested": self.flatten_all_requested,
            "ibkr_connected": snapshot.connected,
            "advisor_mode_enabled": self.advisor_mode_enabled,
            "execution_mode": self.execution_mode,
            "strategy_name": self.config.strategy_name,
            "bot_version": self.config.bot_version,
            "open_positions_count": len(snapshot.positions),
            "pending_orders_count": len(snapshot.orders),
            "active_proposal_status": self.active_proposal.proposal_status,
            "active_proposal_symbol": self.active_proposal.symbol,
            "market_status": self.market_session_state.title(),
            "market_session_state": self.market_session_state,
            "scan_status": self.scan_status,
            "backtest_status": self.backtest_status,
            "backtest_progress": self.backtest_progress,
            "last_backtest_at": self.last_backtest_at,
            "last_backtest_run_id": self.last_backtest_run_id,
            "research_status": self.research_status,
            "research_progress": self.research_progress,
            "research_last_loop_id": self.research_last_loop_id,
            "research_completed_loops": self.research_completed_loops,
            "research_stop_requested": self.research_stop_requested,
            "research_target_met": self.research_target_met,
            "daily_lock": self.runtime_state.get("daily_lock", False),
            "weekly_lock": self.runtime_state.get("weekly_lock", False),
            "kill_switch_active": self.runtime_state.get("kill_switch_active", False),
            "last_scan_at": self.last_scan_at,
            "last_signal_at": self.last_signal_at,
            "last_reconnect_at": self.last_reconnect_at,
            "last_error": self.last_error,
        }
        now = utc_now()
        heartbeat_due = self.last_heartbeat_write_at is None or (now - self.last_heartbeat_write_at).total_seconds() >= 15
        if heartbeat_due or status_payload != self.last_status_payload:
            self.runtime_doc("system", "status").set({**status_payload, "last_heartbeat": firestore.SERVER_TIMESTAMP, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            self.count_write("system_status")
            self.last_status_payload = status_payload
            self.last_heartbeat_write_at = now
        finance_payload = dict(account)
        if finance_payload != self.last_finance_payload:
            self.runtime_doc("finance", "account").set({**finance_payload, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            self.count_write("finance_account")
            self.last_finance_payload = finance_payload
        risk_payload = {
            "daily_pnl_pct": safe_float(account.get("today_pnl_pct")),
            "open_risk_pct": safe_float(self.runtime_state.get("portfolio_risk_pct", 0.0)),
            "exposure_pct": (safe_float(account.get("total_market_value")) / safe_float(account.get("net_liquidation"), 1.0) * 100.0) if safe_float(account.get("net_liquidation")) else 0.0,
            "max_dd_pct": safe_float(account.get("max_drawdown_pct")),
            "open_positions": len(snapshot.positions),
            "trades_today": int(self.runtime_state.get("new_trades_today", 0)),
            "daily_lock": self.runtime_state.get("daily_lock", False),
            "weekly_lock": self.runtime_state.get("weekly_lock", False),
            "kill_switch_active": self.runtime_state.get("kill_switch_active", False),
        }
        if risk_payload != self.last_risk_payload:
            self.runtime_doc("risk", "state").set({**risk_payload, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            self.count_write("risk_state")
            self.last_risk_payload = risk_payload
        self.replace_collection("positions", snapshot.positions, "symbol")
        self.replace_collection("orders", snapshot.orders, "order_id")
        self.upsert_trades(snapshot.trades)

    def publish_proposal(self) -> None:
        payload = self.active_proposal.to_firestore()
        comparable = {k: v for k, v in payload.items() if k != "updated_at"}
        if comparable != self.last_proposal_payload:
            self.proposal_doc().set({**payload, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            self.count_write("proposal_current")
            self.last_proposal_payload = comparable

    def replace_collection(self, collection_name: str, rows: list[dict[str, Any]], key_field: str) -> None:
        signature = repr(sorted([{k: v for k, v in row.items() if k != "updated_at"} for row in rows], key=lambda row: str(row.get(key_field) or "")))
        attr = "last_positions_signature" if collection_name == "positions" else "last_orders_signature"
        if getattr(self, attr) == signature:
            return
        docs = list(self.runtime_collection(collection_name).stream())
        batch = self.db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            self.count_write(f"{collection_name}_delete")
        for idx, row in enumerate(rows):
            doc_id = str(row.get(key_field) or f"{collection_name}-{idx}")
            batch.set(self.runtime_collection(collection_name).document(doc_id), {**row, "updated_at": firestore.SERVER_TIMESTAMP})
            self.count_write(f"{collection_name}_set")
        batch.commit()
        setattr(self, attr, signature)

    def upsert_trades(self, trades: list[dict[str, Any]]) -> None:
        signature = repr(sorted(str(trade.get("execution_id")) for trade in trades))
        if self.last_trade_signature == signature:
            return
        batch = self.db.batch()
        for trade in trades:
            batch.set(self.runtime_collection("trades").document(str(trade["execution_id"])), trade, merge=True)
            self.count_write("trades_set")
        batch.commit()
        self.last_trade_signature = signature

    def track_connection_transition(self, connected: bool) -> None:
        if self.last_logged_connection is None:
            self.last_logged_connection = connected
            return
        if connected != self.last_logged_connection:
            if connected:
                self.set_advisor_mode(False)
                self.log_event("info", f"{self.config.label} IBKR connection established.", source="broker")
            else:
                self.log_event("error", f"{self.config.label} IBKR connection lost.", source="broker")
            self.last_logged_connection = connected
