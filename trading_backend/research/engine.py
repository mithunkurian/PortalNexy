from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from trading_backend.common import utc_now
from trading_backend.models import BacktestRequest, BacktestRun, ResearchLoopRecord, ResearchRequest


FAMILY_LIBRARY: dict[str, dict[str, object]] = {
    "SWG": {
        "template_key": "v1.2_pullback_long",
        "label": "Daily Swing Pullback",
        "description": "Daily-bar swing pullback strategy with strict regime, breakout, and risk gates. It is selective, low-frequency, and intended to propose or execute only the cleanest long setups.",
    },
    "EMA": {
        "template_key": "bluechip_ema_9_21_intraday",
        "label": "EMA Trend",
        "description": "Hidden intraday long-only trend variant on a fixed blue-chip basket. It uses EMA crossover structure, volume confirmation, and capped daily trade frequency.",
    },
    "MOM": {
        "template_key": "mtf_mom_intraday",
        "label": "MTF Momentum",
        "description": "Hidden multi-timeframe momentum variant combining higher-timeframe trend confirmation with lower-timeframe pullback or continuation entries.",
    },
    "BRK": {
        "template_key": "spy_orb_retest",
        "label": "SPY ORB Retest",
        "description": "Hidden SPY opening-range breakout/retest family designed to find higher-conviction intraday expansion moves with same-day exits.",
    },
    "SCP": {
        "template_key": "bluechip_scalp_02pct",
        "label": "Bluechip Scalper",
        "description": "Hidden short-hold intraday scalping family on a fixed blue-chip basket, designed to recycle capital through repeated small-risk, fast-exit trades.",
    },
    "TOP": {
        "template_key": "intraday_top_mover_10_to_11",
        "label": "Top Mover Rotation",
        "description": "Hidden intraday relative-strength family that rotates into the strongest opening blue-chip mover after a supervised ranking window.",
    },
}

SEED_FAMILY_BY_TEMPLATE = {
    "v1.2_pullback_long": "SWG",
    "bluechip_ema_9_21_intraday": "EMA",
    "mtf_mom_intraday": "MOM",
    "spy_orb_retest": "BRK",
    "bluechip_scalp_02pct": "SCP",
    "intraday_top_mover_10_to_11": "TOP",
}


@dataclass
class CandidateState:
    strategy_key: str
    family_id: str
    loop_index: int
    description: str
    template_key: str
    strategy_params: dict[str, object]


@dataclass
class FamilySnapshot:
    family_id: str
    loops: int = 0
    best_score: float = 0.0
    consecutive_zero_trades: int = 0
    consecutive_low_trade_loops: int = 0
    consecutive_flat_scores: int = 0
    consecutive_degrading_scores: int = 0


class ResearchLoopEngine:
    def __init__(self, runtime_id: str, base_dir: str | Path) -> None:
        self.runtime_id = runtime_id
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.base_dir / "strategy_loops.jsonl"
        self.md_path = self.base_dir / "strategy_loops.md"

    def run(
        self,
        request: ResearchRequest,
        run_backtest: Callable[[BacktestRequest, Callable[[str], None] | None], BacktestRun],
        publish_loop: Callable[[ResearchLoopRecord, BacktestRun], None],
        stop_requested: Callable[[], bool],
        progress_cb: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        current = self._seed_candidate(request.seed_strategy_key)
        previous_score: float | None = None
        completed_loops = 0
        target_met = False
        final_record: ResearchLoopRecord | None = None
        family_history: dict[str, FamilySnapshot] = {}
        tried_families: list[str] = [current.family_id]

        for _ in range(max(1, request.max_loops)):
            if stop_requested():
                break

            loop_id = f"{current.family_id}_{current.loop_index}"
            current.strategy_key = loop_id
            if progress_cb:
                progress_cb(f"Loop {completed_loops + 1}/{request.max_loops}: testing {loop_id} ({current.template_key})")

            bt_request = BacktestRequest(
                lookback_days=request.lookback_days,
                capital_sek=request.capital_sek,
                strategy_key=current.strategy_key,
                symbols=request.symbols,
                data_source=request.data_source,
                strategy_params={"template_key": current.template_key, **current.strategy_params},
            )
            result = run_backtest(bt_request, progress_cb)
            completed_loops += 1

            annual_return_pct = self._annual_return_pct(request.lookback_days, result)
            score = self._score(annual_return_pct, result.max_dd, result.sharpe, result.trades)
            snapshot = family_history.setdefault(current.family_id, FamilySnapshot(current.family_id))
            self._update_family_snapshot(snapshot, result, score)

            next_candidate, branch_reason = self._design_next_candidate(
                current=current,
                request=request,
                result=result,
                previous_score=previous_score,
                snapshot=snapshot,
                tried_families=tried_families,
            )
            if next_candidate and next_candidate.family_id not in tried_families:
                tried_families.append(next_candidate.family_id)

            record = self._build_record(
                loop_id=loop_id,
                current=current,
                request=request,
                result=result,
                previous_score=previous_score,
                next_candidate=next_candidate,
                branch_reason=branch_reason,
            )
            self._append_logs(record)
            publish_loop(record, result)
            previous_score = record.strategy_score
            final_record = record

            if record.target_met:
                target_met = True
                break
            if not next_candidate:
                break
            current = next_candidate

        return {
            "completed_loops": completed_loops,
            "target_met": target_met,
            "last_loop_id": final_record.loop_id if final_record else None,
            "last_strategy_key": final_record.strategy_key if final_record else None,
            "last_score": final_record.strategy_score if final_record else None,
        }

    def _seed_candidate(self, seed_strategy_key: str) -> CandidateState:
        family_id = SEED_FAMILY_BY_TEMPLATE.get(seed_strategy_key, "SWG")
        family = FAMILY_LIBRARY[family_id]
        return CandidateState(
            strategy_key=family_id + "_1",
            family_id=family_id,
            loop_index=1,
            description=str(family["description"]),
            template_key=str(family["template_key"]),
            strategy_params=self._initial_params_for_family(family_id),
        )

    def _initial_params_for_family(self, family_id: str) -> dict[str, object]:
        if family_id == "SWG":
            return {}
        if family_id == "EMA":
            return {
                "fast_ema": 8,
                "slow_ema": 21,
                "volume_multiplier": 1.15,
                "stop_pct": 0.006,
                "target_pct": 0.018,
                "max_trades_per_day": 2,
                "risk_frac": 0.008,
            }
        if family_id == "MOM":
            return {
                "higher_tf_ema_len": 20,
                "higher_tf_adx_threshold": 18,
                "entry_pullback_bars": 2,
                "volume_multiplier": 1.1,
                "stop_atr_mult": 1.0,
                "tp1_r": 1.5,
                "tp2_r": 3.0,
                "risk_frac": 0.01,
                "max_trades_per_day": 3,
            }
        if family_id == "BRK":
            return {
                "or_minutes": 25,
                "max_or_width_pct": 1.2,
                "vol_filter_mult": 1.0,
                "breakout_vol_mult": 1.35,
                "tp1_r": 1.75,
                "tp2_r": 4.0,
                "risk_frac": 0.012,
            }
        if family_id == "SCP":
            return {
                "profit_target_pct": 0.25,
                "stop_pct": 0.18,
                "ranking_window_bars": 3,
                "max_trades_per_day": 8,
                "risk_frac": 0.005,
            }
        if family_id == "TOP":
            return {
                "selection_count": 3,
                "buy_hour": 10,
                "buy_minute": 0,
                "sell_hour": 11,
                "sell_minute": 0,
                "min_move_pct": 0.15,
            }
        return {}

    def _design_next_candidate(
        self,
        current: CandidateState,
        request: ResearchRequest,
        result: BacktestRun,
        previous_score: float | None,
        snapshot: FamilySnapshot,
        tried_families: list[str],
    ) -> tuple[CandidateState | None, str]:
        annual_return_pct = self._annual_return_pct(request.lookback_days, result)
        target_met = annual_return_pct >= 20.0 and result.max_dd <= 30.0 and result.sharpe >= 1.0
        if target_met:
            return None, "target_met"

        if self._branch_exhausted(snapshot):
            next_family = self._next_family_to_try(tried_families, prefer_after=current.family_id)
            if not next_family:
                return None, "all_families_exhausted"
            return self._make_candidate(next_family, 1), f"branch_exhausted_{snapshot.family_id.lower()}"

        next_index = current.loop_index + 1
        return self._improved_candidate(current, next_index), "improve_same_family"

    def _branch_exhausted(self, snapshot: FamilySnapshot) -> bool:
        if snapshot.consecutive_zero_trades >= 2:
            return True
        if snapshot.consecutive_low_trade_loops >= 3:
            return True
        if snapshot.consecutive_flat_scores >= 3:
            return True
        if snapshot.consecutive_degrading_scores >= 3:
            return True
        if snapshot.loops >= 6 and snapshot.best_score < 60.0:
            return True
        return False

    def _update_family_snapshot(self, snapshot: FamilySnapshot, result: BacktestRun, score: float) -> None:
        prior_best = snapshot.best_score
        snapshot.loops += 1
        snapshot.best_score = max(snapshot.best_score, score)
        snapshot.consecutive_zero_trades = snapshot.consecutive_zero_trades + 1 if result.trades == 0 else 0
        snapshot.consecutive_low_trade_loops = snapshot.consecutive_low_trade_loops + 1 if result.trades < 20 else 0
        if abs(score - prior_best) <= 1.0:
            snapshot.consecutive_flat_scores += 1
        else:
            snapshot.consecutive_flat_scores = 0
        if prior_best > 0 and score <= prior_best:
            snapshot.consecutive_degrading_scores += 1
        else:
            snapshot.consecutive_degrading_scores = 0

    def _next_family_to_try(self, tried_families: list[str], prefer_after: str | None = None) -> str | None:
        order = ["EMA", "MOM", "BRK", "SCP", "TOP"]
        if prefer_after in order:
            start = order.index(prefer_after) + 1
            rotated = order[start:] + order[:start]
        else:
            rotated = order
        for family_id in rotated:
            if family_id not in tried_families:
                return family_id
        return None

    def _make_candidate(self, family_id: str, loop_index: int) -> CandidateState:
        family = FAMILY_LIBRARY[family_id]
        descriptions = {
            "EMA": "Generated EMA trend variant with tighter risk, stronger volume confirmation, and a cleaner long-only blue-chip basket profile.",
            "MOM": "Generated multi-timeframe momentum variant with higher-timeframe trend confirmation and lower-timeframe timing to improve trade quality.",
            "BRK": "Generated SPY opening-range breakout/retest variant with width, breakout-volume, and reward controls for same-day directional trading.",
            "SCP": "Generated intraday blue-chip scalping variant that seeks many short-duration trades with strict stop/target recycling.",
            "TOP": "Generated relative-strength rotation variant that ranks opening movers and rotates into the strongest liquid name intraday.",
            "SWG": str(family["description"]),
        }
        return CandidateState(
            strategy_key=f"{family_id}_{loop_index}",
            family_id=family_id,
            loop_index=loop_index,
            description=descriptions.get(family_id, str(family["description"])),
            template_key=str(family["template_key"]),
            strategy_params=self._initial_params_for_family(family_id),
        )

    def _improved_candidate(self, current: CandidateState, next_index: int) -> CandidateState:
        prior = current.strategy_params or {}
        if current.family_id == "EMA":
            return CandidateState(
                strategy_key="",
                family_id="EMA",
                loop_index=next_index,
                description="Generated EMA trend revision with slightly slower confirmation, stronger volume filtering, and asymmetric reward/risk tuning to improve Sharpe.",
                template_key="bluechip_ema_9_21_intraday",
                strategy_params={
                    "fast_ema": min(15, int(prior.get("fast_ema", 8)) + 1),
                    "slow_ema": min(40, int(prior.get("slow_ema", 21)) + 2),
                    "volume_multiplier": round(min(1.8, float(prior.get("volume_multiplier", 1.15)) + 0.08), 2),
                    "stop_pct": round(max(0.004, float(prior.get("stop_pct", 0.006)) - 0.0004), 4),
                    "target_pct": round(min(0.03, float(prior.get("target_pct", 0.018)) + 0.003), 4),
                    "max_trades_per_day": max(1, int(prior.get("max_trades_per_day", 2))),
                    "risk_frac": round(max(0.0045, float(prior.get("risk_frac", 0.008)) - 0.0005), 4),
                },
            )
        if current.family_id == "MOM":
            return CandidateState(
                strategy_key="",
                family_id="MOM",
                loop_index=next_index,
                description="Generated MTF momentum revision with stricter higher-timeframe trend quality, stronger volume confirmation, and wider winners to improve annualized return.",
                template_key="mtf_mom_intraday",
                strategy_params={
                    "higher_tf_ema_len": min(35, int(prior.get("higher_tf_ema_len", 20)) + 2),
                    "higher_tf_adx_threshold": min(35, int(prior.get("higher_tf_adx_threshold", 18)) + 2),
                    "entry_pullback_bars": min(4, int(prior.get("entry_pullback_bars", 2)) + 1),
                    "volume_multiplier": round(min(1.8, float(prior.get("volume_multiplier", 1.1)) + 0.08), 2),
                    "stop_atr_mult": round(max(0.8, float(prior.get("stop_atr_mult", 1.0)) - 0.05), 2),
                    "tp1_r": round(min(2.5, float(prior.get("tp1_r", 1.5)) + 0.25), 2),
                    "tp2_r": round(min(5.0, float(prior.get("tp2_r", 3.0)) + 0.4), 2),
                    "risk_frac": round(max(0.006, float(prior.get("risk_frac", 0.01)) - 0.0005), 4),
                    "max_trades_per_day": max(1, int(prior.get("max_trades_per_day", 3)) - 1),
                },
            )
        if current.family_id == "BRK":
            return CandidateState(
                strategy_key="",
                family_id="BRK",
                loop_index=next_index,
                description="Generated SPY opening-range retest revision with a narrower opening range, stricter breakout volume confirmation, and a slightly tighter risk budget to improve risk-adjusted returns.",
                template_key="spy_orb_retest",
                strategy_params={
                    "or_minutes": max(10, int(prior.get("or_minutes", 25)) - 5),
                    "max_or_width_pct": round(max(0.7, float(prior.get("max_or_width_pct", 1.2)) - 0.1), 2),
                    "vol_filter_mult": round(min(1.8, float(prior.get("vol_filter_mult", 1.0)) + 0.08), 2),
                    "breakout_vol_mult": round(min(2.0, float(prior.get("breakout_vol_mult", 1.35)) + 0.1), 2),
                    "tp1_r": round(min(3.0, float(prior.get("tp1_r", 1.75)) + 0.25), 2),
                    "tp2_r": round(max(2.0, float(prior.get("tp2_r", 4.0)) - 0.4), 2),
                    "risk_frac": round(max(0.006, float(prior.get("risk_frac", 0.012)) - 0.0008), 4),
                },
            )
        if current.family_id == "SCP":
            return CandidateState(
                strategy_key="",
                family_id="SCP",
                loop_index=next_index,
                description="Generated blue-chip scalping revision with a slightly wider target, lower stop distance, and more selective ranking window to improve expectancy.",
                template_key="bluechip_scalp_02pct",
                strategy_params={
                    "profit_target_pct": round(min(0.45, float(prior.get("profit_target_pct", 0.25)) + 0.03), 2),
                    "stop_pct": round(max(0.10, float(prior.get("stop_pct", 0.18)) - 0.01), 2),
                    "ranking_window_bars": min(6, int(prior.get("ranking_window_bars", 3)) + 1),
                    "max_trades_per_day": max(3, int(prior.get("max_trades_per_day", 8)) - 1),
                    "risk_frac": round(max(0.003, float(prior.get("risk_frac", 0.005)) - 0.0004), 4),
                },
            )
        if current.family_id == "TOP":
            return CandidateState(
                strategy_key="",
                family_id="TOP",
                loop_index=next_index,
                description="Generated top-mover rotation revision with a narrower candidate set and a slightly later confirmation window to avoid noisy opening moves.",
                template_key="intraday_top_mover_10_to_11",
                strategy_params={
                    "selection_count": max(1, int(prior.get("selection_count", 3)) - 1),
                    "buy_hour": 10,
                    "buy_minute": min(30, int(prior.get("buy_minute", 0)) + 5),
                    "sell_hour": 11,
                    "sell_minute": min(45, int(prior.get("sell_minute", 0)) + 10),
                    "min_move_pct": round(min(0.7, float(prior.get("min_move_pct", 0.15)) + 0.05), 2),
                },
            )
        return self._make_candidate("EMA", 1)

    def _append_logs(self, record: ResearchLoopRecord) -> None:
        payload = record.to_dict()
        with self.jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
        md_lines = [
            f"## {record.loop_id}",
            f"- Timestamp: {record.timestamp.isoformat()}",
            f"- Strategy: {record.strategy_key}",
            f"- Result: {record.result}",
            f"- Score: {record.strategy_score}" + (f" (prev {record.previous_score})" if record.previous_score is not None else ""),
            f"- Annual Return: {record.annual_return_pct:.2f}%",
            f"- Max Drawdown: {record.max_drawdown_pct:.2f}%",
            f"- Sharpe: {record.sharpe:.2f}",
            f"- Trades: {record.trades}",
            f"- Decision: {record.decision}",
            f"- New Strategy ID: {record.new_strategy_id or '—'}",
            "",
            f"Strategy description: {record.strategy_description}",
            "",
            f"RCA: {record.rca_result}",
            "",
            f"Fix: {record.fix}",
            "",
        ]
        with self.md_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(md_lines) + "\n")

    def _build_record(
        self,
        loop_id: str,
        current: CandidateState,
        request: ResearchRequest,
        result: BacktestRun,
        previous_score: float | None,
        next_candidate: CandidateState | None,
        branch_reason: str,
    ) -> ResearchLoopRecord:
        annual_return_pct = self._annual_return_pct(request.lookback_days, result)
        score = self._score(annual_return_pct, result.max_dd, result.sharpe, result.trades)
        target_met = annual_return_pct >= 20.0 and result.max_dd <= 30.0 and result.sharpe >= 1.0
        rca_needed = not target_met
        rca_text = self._rca_text(current, annual_return_pct, result, branch_reason)
        decision = "target met" if target_met else ("improve" if next_candidate and next_candidate.family_id == current.family_id else "new strategy")
        fix_text = "No fix required. Preserve the current ruleset and move to robustness checks." if target_met else self._fix_text(current, result, branch_reason)
        new_strategy_id = f"{next_candidate.family_id}_{next_candidate.loop_index}" if next_candidate else None
        return ResearchLoopRecord(
            loop_id=loop_id,
            family_id=current.family_id,
            strategy_key=current.strategy_key,
            strategy_description=current.description,
            result="Pass" if target_met else "Failed",
            strategy_score=score,
            previous_score=previous_score,
            annual_return_pct=round(annual_return_pct, 2),
            return_pct=result.return_pct,
            max_drawdown_pct=result.max_dd,
            sharpe=result.sharpe,
            trades=result.trades,
            win_rate_pct=result.win_rate_pct,
            rca_needed=rca_needed,
            rca_result=rca_text,
            fix=fix_text,
            decision=decision,
            new_strategy_id=new_strategy_id,
            target_met=target_met,
            timestamp=utc_now(),
            run_id=result.run_id,
            data_source=request.data_source,
            lookback_days=request.lookback_days,
            capital_sek=request.capital_sek,
            notes=result.notes,
        )

    def _annual_return_pct(self, lookback_days: int, result: BacktestRun) -> float:
        counters = (result.meta or {}).get("counters") or {}
        trading_days = max(int(counters.get("scan_days") or lookback_days or 252), 1)
        years = max(trading_days / 252.0, 1 / 252.0)
        return ((1.0 + (result.return_pct / 100.0)) ** (1.0 / years) - 1.0) * 100.0 if result.return_pct > -100.0 else -100.0

    def _score(self, annual_return_pct: float, max_dd: float, sharpe: float, trades: int) -> float:
        return_component = min(max(annual_return_pct / 20.0, 0.0), 1.0)
        sharpe_component = min(max(sharpe / 1.0, 0.0), 1.0)
        drawdown_component = 1.0 if max_dd <= 0 else min(30.0 / max(max_dd, 0.01), 1.0)
        trade_component = min(max(trades / 50.0, 0.0), 1.0)
        return round(100.0 * ((0.45 * return_component) + (0.30 * sharpe_component) + (0.15 * drawdown_component) + (0.10 * trade_component)), 1)

    def _rca_text(self, current: CandidateState, annual_return_pct: float, result: BacktestRun, branch_reason: str) -> str:
        misses: list[str] = []
        if annual_return_pct < 20.0:
            misses.append(f"annual return is {annual_return_pct:.2f}% versus the 20% target")
        if result.max_dd > 30.0:
            misses.append(f"max drawdown is {result.max_dd:.2f}% versus the 30% ceiling")
        if result.sharpe < 1.0:
            misses.append(f"Sharpe is {result.sharpe:.2f} versus the 1.00 target")
        if result.trades < 20:
            misses.append(f"trade count is only {result.trades}, which limits confidence")
        if not misses:
            return "The loop met all target constraints, so no RCA is required."
        if branch_reason.startswith("branch_exhausted"):
            return (
                f"{current.strategy_key} failed because {('; '.join(misses[:4]))}. "
                f"This branch is now exhausted: repeated low-information results show the current family is too restrictive or too weak to optimize further."
            )[:300]
        return (
            f"{current.strategy_key} failed because {('; '.join(misses[:4]))}. "
            f"The failure points to weak edge quality, insufficient opportunity frequency, or risk-adjusted returns that do not justify the capital base."
        )[:300]

    def _fix_text(self, current: CandidateState, result: BacktestRun, branch_reason: str) -> str:
        if branch_reason.startswith("branch_exhausted"):
            return "Abandon this family and branch to a new hidden strategy family with materially different entry structure, trade frequency, and opportunity set."[:300]
        if current.family_id == "SWG":
            return "Replace the inactive daily swing logic with a hidden intraday family that can generate more opportunities while preserving hard risk limits."[:300]
        if current.family_id == "EMA":
            return "Tune EMA spacing, tighten risk per trade, and raise volume confirmation so the next hidden EMA variant only trades cleaner trend transitions."[:300]
        if current.family_id == "MOM":
            return "Tighten higher-timeframe trend confirmation and improve lower-timeframe timing so the next hidden momentum variant keeps opportunity flow but raises trade quality."[:300]
        if current.family_id == "BRK":
            return "Adjust opening-range width, breakout-volume filter, and reward structure; if the branch starves, abandon it rather than continuing tiny revisions."[:300]
        if current.family_id == "SCP":
            return "Tighten the stop/target mix and reduce low-quality churn so the next scalping revision improves expectancy rather than just turnover."[:300]
        if current.family_id == "TOP":
            return "Narrow the mover universe, tighten ranking thresholds, and slightly delay entry timing so the next top-mover revision avoids noisy opening reversals."[:300]
        return "Create a new hidden strategy variant and do not loop across the public strategy list."[:300]
