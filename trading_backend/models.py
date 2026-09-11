from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class BrokerSnapshot:
    connected: bool
    account: dict[str, Any] = field(default_factory=dict)
    positions: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RuntimeConfig:
    runtime_id: str
    strategy_name: str
    bot_version: str
    use_mock_broker: bool
    poll_secs: int
    base_currency: str = "SEK"
    account_size_sek: float = 10000.0
    metadata_path: str | None = None
    sqlite_path: str | None = None
    backtest_lookback_days: int = 756

    @property
    def label(self) -> str:
        return "Paper" if self.runtime_id == "paper" else "Live"


@dataclass
class WatchlistItem:
    symbol: str
    name: str
    sector: str
    asset_type: str
    large_cap: bool
    liquid_etf: bool
    min_avg_volume: int
    max_spread_bps: float
    earnings_dates: list[date] = field(default_factory=list)
    enabled: bool = True


@dataclass
class StrategyCandidate:
    symbol: str
    sector: str
    score: float
    confidence_score: float
    close: float
    previous_high: float
    previous_low: float
    pullback_low: float
    atr: float
    rsi: float
    ma50: float
    ma200: float
    ema10: float
    avg_volume: float
    breakout_volume: float
    pullback_days: int
    entry_trigger_price: float
    stop_price: float
    risk_per_share: float
    rationale: str
    setup_date: date
    valid_for_date: date


@dataclass
class RiskDecision:
    passed: bool
    reason: str
    checks: dict[str, Any]
    quantity: int = 0
    notional_usd: float = 0.0
    risk_amount_usd: float = 0.0
    risk_amount_sek: float = 0.0


@dataclass
class PositionPlan:
    symbol: str
    quantity: int
    entry_price: float
    stop_price: float
    target_1r: float
    target_2r: float
    ema10: float
    sector: str
    risk_per_share: float
    partial_taken: bool = False
    stop_order_id: str | None = None
    entry_order_id: str | None = None
    trade_id: str | None = None


@dataclass
class Proposal:
    proposal_id: str | None
    symbol: str | None
    side: str | None
    quantity: int
    order_type: str | None
    entry_trigger_price: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward: float | None
    risk_per_share: float | None
    score: float | None
    confidence_score: float | None
    sector: str | None
    strategy_tag: str
    rationale: str
    proposal_status: str
    approval_required: bool
    mode: str
    created_at: datetime
    last_validated_at: datetime
    expires_at: datetime | None
    valid_for_date: date | None = None
    invalid_reason: str | None = None
    entry_order_id: str | None = None
    validation_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_firestore(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "entry_trigger_price": self.entry_trigger_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "risk_per_share": self.risk_per_share,
            "score": self.score,
            "confidence_score": self.confidence_score,
            "sector": self.sector,
            "strategy_tag": self.strategy_tag,
            "rationale": self.rationale,
            "proposal_status": self.proposal_status,
            "approval_required": self.approval_required,
            "mode": self.mode,
            "created_at": self.created_at,
            "last_validated_at": self.last_validated_at,
            "expires_at": self.expires_at,
            "valid_for_date": self.valid_for_date.isoformat() if self.valid_for_date else None,
            "invalid_reason": self.invalid_reason,
            "entry_order_id": self.entry_order_id,
            "validation_snapshot": self.validation_snapshot,
        }


@dataclass
class BacktestRequest:
    lookback_days: int = 756
    capital_sek: float = 10000.0
    strategy_key: str = "v1.2_pullback_long"
    symbols: list[str] = field(default_factory=list)
    data_source: str = "ibkr"
    strategy_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestRun:
    run_id: str
    runtime_id: str
    strategy: str
    period: str
    return_pct: float
    sharpe: float
    max_dd: float
    trades: int
    win_rate_pct: float
    timestamp: datetime
    status: str
    notes: str
    symbols_tested: int
    daily_bars_mode: str = "completed_daily_bars"
    entry_timing_mode: str = "1min_1015_et_validation"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_firestore(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "runtime_id": self.runtime_id,
            "strategy": self.strategy,
            "period": self.period,
            "return_pct": self.return_pct,
            "sharpe": self.sharpe,
            "max_dd": self.max_dd,
            "trades": self.trades,
            "win_rate_pct": self.win_rate_pct,
            "timestamp": self.timestamp,
            "status": self.status,
            "notes": self.notes,
            "symbols_tested": self.symbols_tested,
            "daily_bars_mode": self.daily_bars_mode,
            "entry_timing_mode": self.entry_timing_mode,
            "meta": self.meta,
        }


@dataclass
class ResearchRequest:
    seed_strategy_key: str
    lookback_days: int = 1260
    capital_sek: float = 10000.0
    symbols: list[str] = field(default_factory=list)
    data_source: str = "alpaca"
    max_loops: int = 50


@dataclass
class ResearchLoopRecord:
    loop_id: str
    family_id: str
    strategy_key: str
    strategy_description: str
    result: str
    strategy_score: float
    previous_score: float | None
    annual_return_pct: float
    return_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: int
    win_rate_pct: float
    rca_needed: bool
    rca_result: str
    fix: str
    decision: str
    new_strategy_id: str | None
    target_met: bool
    timestamp: datetime
    run_id: str
    data_source: str
    lookback_days: int
    capital_sek: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "family_id": self.family_id,
            "strategy_key": self.strategy_key,
            "strategy_description": self.strategy_description,
            "result": self.result,
            "strategy_score": self.strategy_score,
            "previous_score": self.previous_score,
            "annual_return_pct": self.annual_return_pct,
            "return_pct": self.return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe": self.sharpe,
            "trades": self.trades,
            "win_rate_pct": self.win_rate_pct,
            "rca_needed": self.rca_needed,
            "rca_result": self.rca_result,
            "fix": self.fix,
            "decision": self.decision,
            "new_strategy_id": self.new_strategy_id,
            "target_met": self.target_met,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "data_source": self.data_source,
            "lookback_days": self.lookback_days,
            "capital_sek": self.capital_sek,
            "notes": self.notes,
        }
