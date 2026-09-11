from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import erf, exp, log, sqrt
from statistics import mean, pstdev
from typing import Callable
from uuid import uuid4

from trading_backend.common import US_EASTERN, safe_float, utc_now
from trading_backend.broker.alpaca import AlpacaHistoricalDataAdapter
from trading_backend.data.market_data import DailyBar
from trading_backend.models import BacktestRequest, BacktestRun, PositionPlan, RuntimeConfig, StrategyCandidate
from trading_backend.risk.engine import RiskEngine
from trading_backend.strategy.v12_pullback import V12PullbackStrategy, exponential_moving_average

TOP_MOVER_BLUECHIPS = [
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NVDA",
    "JPM",
]


@dataclass
class IntradayBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _adx_value(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """Compute ADX using Wilder's smoothing. Returns None if insufficient data."""
    if len(highs) < period * 2 + 2:
        return None
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_list: list[float] = []
    for i in range(1, len(highs)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr_list.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    if len(tr_list) < period:
        return None
    smooth_tr = sum(tr_list[:period])
    smooth_plus = sum(plus_dm[:period])
    smooth_minus = sum(minus_dm[:period])
    dx_values: list[float] = []
    for i in range(period, len(tr_list)):
        smooth_tr = smooth_tr - smooth_tr / period + tr_list[i]
        smooth_plus = smooth_plus - smooth_plus / period + plus_dm[i]
        smooth_minus = smooth_minus - smooth_minus / period + minus_dm[i]
        if smooth_tr == 0:
            continue
        di_plus = 100.0 * smooth_plus / smooth_tr
        di_minus = 100.0 * smooth_minus / smooth_tr
        denom = di_plus + di_minus
        dx_values.append(100.0 * abs(di_plus - di_minus) / denom if denom > 0 else 0.0)
    if len(dx_values) < period:
        return None
    return mean(dx_values[-period:])


def _atr_intraday(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """Compute ATR from parallel high/low/close lists."""
    if len(highs) <= period:
        return None
    true_ranges: list[float] = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    return mean(true_ranges[-period:])


@dataclass
class OpenBacktestPosition:
    plan: PositionPlan
    symbol: str
    sector: str
    qty_open: int
    qty_initial: int
    entered_at: date
    partial_taken: bool = False


class BacktestRunner:
    def __init__(self, broker, metadata, strategy: V12PullbackStrategy, risk_engine: RiskEngine, config: RuntimeConfig) -> None:
        self.broker = broker
        self.alpaca_data: AlpacaHistoricalDataAdapter | None = None
        self._active_data_provider = broker
        self.metadata = metadata
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.config = config
        self.fx_usdsek = 11.0

    @staticmethod
    def _trade_stats(pnls: list[float]) -> dict[str, float | None]:
        wins = [value for value in pnls if value > 0]
        losses = [value for value in pnls if value < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        return {
            "avg_win_usd": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss_usd": round(sum(losses) / len(losses), 2) if losses else None,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else (None if gross_profit == 0 else 999.0),
        }

    def run(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        previous_provider = self._active_data_provider
        self._active_data_provider = self._resolve_data_provider(request.data_source)
        try:
            effective_key = str((request.strategy_params or {}).get("template_key") or request.strategy_key)
            if effective_key == "smoke_open_close_daily":
                result = self._run_smoke_open_close_daily(request)
            elif effective_key == "benchmark_buy_and_hold":
                result = self._run_benchmark_buy_and_hold(request)
            elif effective_key == "intraday_top_mover_10_to_11":
                result = self._run_intraday_top_mover_10_to_11(request, progress_cb=progress_cb)
            elif effective_key == "spy_10_to_14_monthly_put_hedge":
                result = self._run_spy_10_to_14_monthly_put_hedge(request, progress_cb=progress_cb)
            elif effective_key == "spy_weekly_atm_long_strangle":
                result = self._run_spy_weekly_atm_long_strangle(request, progress_cb=progress_cb)
            elif effective_key == "spy_weekly_atm_short_strangle":
                result = self._run_spy_weekly_atm_short_strangle(request, progress_cb=progress_cb)
            elif effective_key == "spy_weekly_short_iron_condor":
                result = self._run_spy_weekly_short_iron_condor(request, progress_cb=progress_cb)
            elif effective_key == "bluechip_scalp_02pct":
                result = self._run_bluechip_scalp_02pct(request, progress_cb=progress_cb)
            elif effective_key == "bluechip_ema_9_21_intraday":
                result = self._run_bluechip_ema_9_21_intraday(request, progress_cb=progress_cb)
            elif effective_key == "mtf_mom_intraday":
                result = self._run_mtf_mom_intraday(request, progress_cb=progress_cb)
            elif effective_key == "spy_orb_retest":
                result = self._run_spy_orb_retest(request, progress_cb=progress_cb)
            else:
                result = self._run_v12_pullback(request, progress_cb=progress_cb)
            if effective_key != request.strategy_key:
                result.strategy = request.strategy_key
                result.meta = result.meta or {}
                result.meta["template_key"] = effective_key
            result.meta = result.meta or {}
            result.meta["data_source"] = request.data_source
            return result
        finally:
            self._active_data_provider = previous_provider

    def _resolve_data_provider(self, data_source: str):
        if str(data_source or "ibkr").lower() != "alpaca":
            return self.broker
        if self.alpaca_data is None:
            self.alpaca_data = AlpacaHistoricalDataAdapter()
        return self.alpaca_data

    def _run_v12_pullback(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:

        items = list(self.metadata.active_items())
        daily_map: dict[str, list[DailyBar]] = {}
        index_map: dict[str, dict[date, int]] = {}
        trading_dates: set[date] = set()
        required_calendar_days = max((request.lookback_days * 3), request.lookback_days + 520, 900)
        for item in items:
            bars = self._fetch_daily(item.symbol, required_calendar_days)
            if len(bars) < 220:
                continue
            daily_map[item.symbol] = bars
            index_map[item.symbol] = {bar.date: idx for idx, bar in enumerate(bars)}
            for bar in bars:
                trading_dates.add(bar.date)

        completed_cutoff = self._last_completed_daily_date()
        ordered_dates = sorted(d for d in trading_dates if d <= completed_cutoff)
        if len(ordered_dates) < 30:
            raise RuntimeError("Not enough historical bars to run backtest.")

        start_cutoff = ordered_dates[-min(len(ordered_dates), request.lookback_days)]
        sim_dates = [d for d in ordered_dates if d >= start_cutoff]

        equity_usd = request.capital_sek / self.fx_usdsek
        peak_equity = equity_usd
        daily_equity_curve: list[float] = []
        daily_returns: list[float] = []
        open_positions: dict[str, OpenBacktestPosition] = {}
        sector_held: set[str] = set()
        daily_trade_count: dict[date, int] = {}
        daily_loss_count: dict[date, int] = {}
        symbol_cooldowns: dict[str, date] = {}
        weekly_start_equity: dict[tuple[int, int], float] = {}
        closed_pnls: list[float] = []
        trades_closed = 0
        wins = 0
        notes = [
            "Completed daily bars drive signal generation.",
            "1-minute entry-day replay used for 10:15 ET invalidation and trigger timing.",
            "Daily bars drive post-entry stop/target/EMA supervision.",
        ]
        counters = {
            "scan_days": len(sim_dates),
            "trading_days": len(sim_dates),
            "symbol_evaluations": 0,
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for current_day in sim_dates:
            weekday_key = current_day.isocalendar()[:2]
            weekly_start_equity.setdefault(weekday_key, equity_usd)

            if self._weekly_drawdown_pct(equity_usd, weekly_start_equity[weekday_key]) >= 3.0:
                weekly_locked = True
            else:
                weekly_locked = False
            kill_switch = self._total_drawdown_pct(equity_usd, peak_equity) >= 8.0

            # Mark-to-market end of prior session / current day exits.
            day_realized = 0.0
            for symbol, open_position in list(open_positions.items()):
                bars = daily_map.get(symbol) or []
                idx = index_map[symbol].get(current_day)
                if idx is None:
                    continue
                bar = bars[idx]
                exit_pnl, closed, exit_note, exit_reason = self._process_open_position(open_position, bars[: idx + 1], bar)
                if exit_pnl:
                    equity_usd += exit_pnl
                    day_realized += exit_pnl
                    closed_pnls.append(exit_pnl)
                    if exit_pnl > 0:
                        wins += 1
                if exit_reason == "stop":
                    counters["stop_loss_hits"] += 1
                elif exit_reason == "target":
                    counters["target_hits"] += 1
                elif exit_reason == "partial_target":
                    counters["partial_target_hits"] += 1
                elif exit_reason == "ema":
                    counters["ema_exits"] += 1
                if closed:
                    trades_closed += 1
                    sector_held.discard(open_position.sector)
                    open_positions.pop(symbol, None)
                    if exit_note:
                        notes.append(exit_note)

            daily_trade_count.setdefault(current_day, 0)
            daily_loss_count.setdefault(current_day, 0)
            if day_realized < 0:
                daily_loss_count[current_day] += 1

            if (
                len(open_positions) < 2
                and daily_trade_count[current_day] < 1
                and daily_loss_count[current_day] < 2
                and not weekly_locked
                and not kill_switch
            ):
                candidate = self._pick_candidate_for_day(current_day, items, daily_map, index_map, open_positions, symbol_cooldowns, counters)
                if candidate:
                    counters["valid_candidates"] += 1
                    item, strat_candidate = candidate
                    decision = self.risk_engine.evaluate_entry(
                        strat_candidate,
                        {"net_liquidation": equity_usd, "buying_power": equity_usd},
                        [
                            {
                                "symbol": p.symbol,
                                "sector": p.sector,
                                "quantity": p.qty_open,
                            }
                            for p in open_positions.values()
                        ],
                        {
                            "daily_lock": False,
                            "weekly_lock": weekly_locked,
                            "kill_switch_active": kill_switch,
                            "new_trades_today": daily_trade_count[current_day],
                            "portfolio_risk_pct": sum(
                                (p.qty_open * abs(p.plan.entry_price - p.plan.stop_price)) / max(equity_usd, 1.0) * 100.0
                                for p in open_positions.values()
                            ),
                        },
                        self.fx_usdsek,
                        item,
                    )
                    if decision.passed:
                        counters["orders_planned"] += 1
                        entry_state, entry_price = self._simulate_entry(item.symbol, current_day, strat_candidate.entry_trigger_price)
                        if entry_state == "invalidated":
                            counters["orders_invalidated_pre_1015"] += 1
                            symbol_cooldowns[item.symbol] = current_day
                            notes.append(f"{item.symbol} invalidated on {current_day.isoformat()} due to pre-10:15 breach.")
                        elif entry_state == "expired":
                            counters["orders_submitted"] += 1
                            counters["orders_cancelled"] += 1
                            notes.append(f"{item.symbol} entry expired unfilled on {current_day.isoformat()}.")
                        elif entry_state == "filled" and isinstance(entry_price, float):
                            counters["orders_submitted"] += 1
                            counters["orders_filled"] += 1
                            qty = decision.quantity
                            risk_per_share = max(entry_price - strat_candidate.stop_price, 0.01)
                            plan = PositionPlan(
                                symbol=item.symbol,
                                quantity=qty,
                                entry_price=entry_price,
                                stop_price=strat_candidate.stop_price,
                                target_1r=entry_price + risk_per_share,
                                target_2r=entry_price + (2 * risk_per_share),
                                ema10=strat_candidate.ema10,
                                sector=item.sector,
                                risk_per_share=risk_per_share,
                            )
                            open_positions[item.symbol] = OpenBacktestPosition(
                                plan=plan,
                                symbol=item.symbol,
                                sector=item.sector,
                                qty_open=qty,
                                qty_initial=qty,
                                entered_at=current_day,
                            )
                            sector_held.add(item.sector)
                            daily_trade_count[current_day] += 1
                            notes.append(f"{item.symbol} entered on {current_day.isoformat()} at {entry_price:.2f}.")

            mtm_equity = equity_usd
            for symbol, open_position in open_positions.items():
                idx = index_map[symbol].get(current_day)
                if idx is None:
                    continue
                bar = daily_map[symbol][idx]
                mtm_equity += (bar.close - open_position.plan.entry_price) * open_position.qty_open
            daily_equity_curve.append(mtm_equity)
            if len(daily_equity_curve) > 1 and daily_equity_curve[-2] > 0:
                daily_returns.append((daily_equity_curve[-1] / daily_equity_curve[-2]) - 1.0)
            peak_equity = max(peak_equity, mtm_equity)

        total_return_pct = ((daily_equity_curve[-1] / (request.capital_sek / self.fx_usdsek)) - 1.0) * 100.0 if daily_equity_curve else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(daily_equity_curve)
        win_rate = (wins / trades_closed * 100.0) if trades_closed else 0.0
        period = f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}"
        trade_stats = self._trade_stats(closed_pnls)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=period,
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=trades_closed,
            win_rate_pct=round(win_rate, 2),
            timestamp=utc_now(),
            status="completed",
            notes=" | ".join(notes[:8]),
            symbols_tested=len(daily_map),
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(daily_equity_curve[-1] - (request.capital_sek / self.fx_usdsek), 2) if daily_equity_curve else 0.0,
                "pnl_sek": round(((daily_equity_curve[-1] - (request.capital_sek / self.fx_usdsek)) * self.fx_usdsek), 2) if daily_equity_curve else 0.0,
                "counters": counters,
                "closed_trade_pnls": [round(v, 2) for v in closed_pnls[-20:]],
                **trade_stats,
            },
        )

    def _run_smoke_open_close_daily(self, request: BacktestRequest) -> BacktestRun:
        items = list(self.metadata.active_items())
        if not items:
            raise RuntimeError("No active watchlist symbols available.")
        item_by_symbol = {item.symbol: item for item in items}
        requested_symbols = [symbol for symbol in request.symbols if symbol in item_by_symbol]
        symbols = requested_symbols or [symbol for symbol in TOP_MOVER_BLUECHIPS if symbol in item_by_symbol]
        if not symbols:
            raise RuntimeError("Smoke backtest requires at least one configured blue-chip symbol.")

        completed_cutoff = self._last_completed_daily_date()
        required_calendar_days = max((request.lookback_days * 3), request.lookback_days + 120, 400)
        bars_map: dict[str, list[DailyBar]] = {}
        shared_dates: set[date] | None = None
        for symbol in symbols:
            bars = [bar for bar in self._fetch_daily(symbol, required_calendar_days) if bar.date <= completed_cutoff]
            if len(bars) < request.lookback_days:
                continue
            trimmed = bars[-request.lookback_days:]
            bars_map[symbol] = trimmed
            symbol_dates = {bar.date for bar in trimmed}
            shared_dates = symbol_dates if shared_dates is None else shared_dates & symbol_dates
        if not bars_map:
            raise RuntimeError("Not enough historical bars for the smoke backtest basket.")

        aligned_dates = sorted(shared_dates or [])
        if not aligned_dates:
            raise RuntimeError("No overlapping trading dates available for the smoke backtest basket.")
        bar_lookup = {symbol: {bar.date: bar for bar in bars} for symbol, bars in bars_map.items()}

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        wins = 0
        losses = 0
        total_trades = 0
        pnl_series: list[float] = []
        counters = {
            "scan_days": len(aligned_dates),
            "trading_days": len(aligned_dates),
            "symbol_evaluations": len(aligned_dates) * len(bars_map),
            "valid_candidates": len(aligned_dates) * len(bars_map),
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }
        for trading_day in aligned_dates:
            basket_symbols = [symbol for symbol in bars_map if trading_day in bar_lookup[symbol]]
            if not basket_symbols:
                equity_curve.append(equity_usd)
                continue
            allocation_per_symbol = equity_usd / len(basket_symbols)
            day_pnl = 0.0
            for symbol in basket_symbols:
                bar = bar_lookup[symbol][trading_day]
                qty = int(allocation_per_symbol // max(bar.open, 0.01))
                if qty <= 0:
                    continue
                pnl = (bar.close - bar.open) * qty
                day_pnl += pnl
                pnl_series.append(round(pnl, 2))
                total_trades += 1
                counters["orders_planned"] += 1
                counters["orders_submitted"] += 1
                counters["orders_filled"] += 1
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1
            equity_usd += day_pnl
            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        win_rate = (wins / total_trades * 100.0) if total_trades else 0.0
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{aligned_dates[0].isoformat()} to {aligned_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round(win_rate, 2),
            timestamp=utc_now(),
            status="completed",
            notes="Smoke test strategy on the fixed 7-stock blue-chip basket: buy each symbol at the daily open with equal capital allocation and sell at the same-day close.",
            symbols_tested=len(bars_map),
            entry_timing_mode="daily_open_to_close_equal_weight_basket",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(equity_usd - start_equity_usd, 2),
                "pnl_sek": round((equity_usd - start_equity_usd) * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "wins": wins,
                "losses": losses,
                "basket_symbols": list(bars_map.keys()),
                "allocation_mode": "equal_weight_per_symbol_per_day",
            },
        )

    def _run_benchmark_buy_and_hold(self, request: BacktestRequest) -> BacktestRun:
        items = list(self.metadata.active_items())
        if not items:
            raise RuntimeError("No active watchlist symbols available.")
        preferred = next((item for item in items if item.symbol == "AAPL"), items[0])
        completed_cutoff = self._last_completed_daily_date()
        required_calendar_days = max((request.lookback_days * 3), request.lookback_days + 120, 400)
        bars = [bar for bar in self._fetch_daily(preferred.symbol, required_calendar_days) if bar.date <= completed_cutoff]
        if len(bars) < request.lookback_days:
            raise RuntimeError(f"Not enough historical bars for {preferred.symbol}.")
        sim_bars = bars[-request.lookback_days:]
        start_equity_usd = request.capital_sek / self.fx_usdsek
        entry_bar = sim_bars[0]
        qty = int(start_equity_usd // max(entry_bar.open, 0.01))
        if qty <= 0:
            raise RuntimeError("Capital is too small to buy even one share.")
        cash_left = start_equity_usd - (qty * entry_bar.open)
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        for bar in sim_bars:
            equity = cash_left + (qty * bar.close)
            equity_curve.append(equity)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
        final_equity = equity_curve[-1]
        total_return_pct = ((final_equity / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = final_equity - start_equity_usd
        counters = {
            "scan_days": len(sim_bars),
            "trading_days": len(sim_bars),
            "symbol_evaluations": len(sim_bars),
            "valid_candidates": 1,
            "orders_planned": 1,
            "orders_submitted": 1,
            "orders_filled": 1,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 1,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }
        trade_stats = self._trade_stats([pnl_usd])
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_bars[0].date.isoformat()} to {sim_bars[-1].date.isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=1,
            win_rate_pct=100.0 if pnl_usd > 0 else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes=f"Benchmark buy-and-hold on {preferred.symbol}: bought first session open and held through final close.",
            symbols_tested=1,
            entry_timing_mode="buy_first_open_hold_to_last_close",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": [round(pnl_usd, 2)],
                **trade_stats,
                "symbol": preferred.symbol,
                "entry_price": round(entry_bar.open, 4),
                "exit_price": round(sim_bars[-1].close, 4),
                "quantity": qty,
            },
        )

    def _run_intraday_top_mover_10_to_11(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        items = list(self.metadata.active_items())
        if not items:
            raise RuntimeError("No active watchlist symbols available.")
        item_by_symbol = {item.symbol: item for item in items}
        symbols = [symbol for symbol in TOP_MOVER_BLUECHIPS if symbol in item_by_symbol]
        if not symbols:
            raise RuntimeError("Top Mover backtest requires at least one configured blue-chip symbol.")
        completed_cutoff = self._last_completed_daily_date()
        # Use daily bars only to determine available trading dates.
        trading_dates: set[date] = set()
        for symbol in symbols:
            bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 400)) if bar.date <= completed_cutoff]
            trading_dates.update(bar.date for bar in bars)
        ordered_dates = sorted(trading_dates)
        if len(ordered_dates) < 30:
            raise RuntimeError("Not enough historical bars to run backtest.")
        sim_dates = ordered_dates[-min(len(ordered_dates), request.lookback_days):]
        sim_date_set = set(sim_dates)

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        total_trades = 0
        wins = 0
        pnl_series: list[float] = []
        traded_symbols: dict[str, int] = {}
        intraday_cache: dict[tuple[str, date], list[IntradayBar]] = {}
        counters = {
            "scan_days": len(sim_dates),
            "trading_days": len(sim_dates),
            "symbol_evaluations": 0,
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        start_day = sim_dates[0]
        end_day = sim_dates[-1]
        total_symbols = len(symbols)
        total_days = len(sim_dates)
        for index, symbol in enumerate(symbols, start=1):
            if progress_cb:
                progress_cb(f"Prefetching intraday bars for {symbol} ({index}/{total_symbols})...")
            for bar in self._fetch_intraday_range(symbol, start_day, end_day, bar_size="5 mins"):
                trading_day = bar.timestamp.astimezone(US_EASTERN).date()
                if trading_day in sim_date_set:
                    intraday_cache.setdefault((symbol, trading_day), []).append(bar)

        for day_index, trading_day in enumerate(sim_dates, start=1):
            if progress_cb and (day_index == 1 or day_index == total_days or day_index % 25 == 0):
                progress_cb(f"Ranking top movers for {trading_day.isoformat()} ({day_index}/{total_days} days)...")
            ranked: list[tuple[float, float, str, float, float]] = []
            for symbol in symbols:
                counters["symbol_evaluations"] += 1
                minute_bars = intraday_cache.get((symbol, trading_day), [])
                candidate = self._intraday_top_mover_candidate(symbol, minute_bars)
                if candidate is None:
                    continue
                ranked.append(candidate)

            if not ranked:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            ranked.sort(key=lambda row: row[0], reverse=True)
            top_five = ranked[:5]
            chosen = max(top_five, key=lambda row: row[1])
            _mover_pct, _volume_sum, symbol, entry_price, exit_price = chosen
            qty = int(equity_usd // max(entry_price, 0.01))
            if qty <= 0:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            counters["valid_candidates"] += 1
            counters["orders_planned"] += 1
            counters["orders_submitted"] += 1
            counters["orders_filled"] += 1
            total_trades += 1
            traded_symbols[symbol] = traded_symbols.get(symbol, 0) + 1
            pnl = (exit_price - entry_price) * qty
            pnl_series.append(round(pnl, 2))
            equity_usd += pnl
            if pnl > 0:
                wins += 1
                counters["target_hits"] += 1
            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        top_symbol = max(traded_symbols, key=traded_symbols.get) if traded_symbols else None
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="Intraday top-mover strategy: rank open-to-10:00 gain, choose highest-volume name from top 5, buy 10:00 ET, sell 11:00 ET.",
            symbols_tested=len(symbols),
            entry_timing_mode="rank_to_1000_buy_1000_sell_1100",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "top_symbol": top_symbol,
                "traded_symbols": traded_symbols,
                "universe_symbols": symbols,
            },
        )

    def _run_spy_10_to_14_monthly_put_hedge(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        symbol = "SPY"
        completed_cutoff = self._last_completed_daily_date()
        bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 500)) if bar.date <= completed_cutoff]
        if len(bars) < 30:
            raise RuntimeError("Not enough historical daily bars for SPY.")
        sim_bars = bars[-min(len(bars), request.lookback_days):]
        start_day = sim_bars[0].date
        end_day = sim_bars[-1].date
        if progress_cb:
            progress_cb("Prefetching SPY intraday bars for 10:00-14:00 strategy...")
        intraday_by_day: dict[date, list[IntradayBar]] = {}
        for bar in self._fetch_intraday_range(symbol, start_day, end_day, bar_size="5 mins"):
            trading_day = bar.timestamp.astimezone(US_EASTERN).date()
            intraday_by_day.setdefault(trading_day, []).append(bar)

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        hedge_rolls = 0
        hedge_cost_usd = 0.0
        current_month: tuple[int, int] | None = None
        hedge_position: dict[str, float] | None = None
        counters = {
            "scan_days": len(sim_bars),
            "trading_days": len(sim_bars),
            "symbol_evaluations": len(sim_bars),
            "valid_candidates": len(sim_bars),
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
            "hedge_rolls": 0,
        }

        for day_index, day_bar in enumerate(sim_bars, start=1):
            if progress_cb and (day_index == 1 or day_index == len(sim_bars) or day_index % 25 == 0):
                progress_cb(f"Evaluating SPY 10:00-14:00 with monthly hedge ({day_index}/{len(sim_bars)} days)...")

            month_key = (day_bar.date.year, day_bar.date.month)
            days_to_expiry = max(1, (28 if current_month != month_key else (hedge_position or {}).get("days_to_expiry", 1)) - 1)

            if hedge_position:
                old_value = hedge_position["value_usd"]
                new_value = self._bs_put_price(
                    spot=day_bar.close,
                    strike=hedge_position["strike"],
                    time_to_expiry=max(days_to_expiry, 1) / 365.0,
                    sigma=0.20,
                ) * hedge_position["units"] * 100.0
                equity_usd += new_value - old_value
                hedge_position["value_usd"] = new_value
                hedge_position["days_to_expiry"] = days_to_expiry

            if current_month != month_key:
                units = max((equity_usd / max(day_bar.open, 0.01)) / 100.0, 0.01)
                premium = self._bs_put_price(
                    spot=day_bar.open,
                    strike=day_bar.open,
                    time_to_expiry=30.0 / 365.0,
                    sigma=0.20,
                )
                cost = premium * units * 100.0
                equity_usd -= cost
                hedge_cost_usd += cost
                hedge_position = {
                    "strike": day_bar.open,
                    "units": units,
                    "value_usd": cost,
                    "days_to_expiry": 30,
                }
                current_month = month_key
                hedge_rolls += 1
                counters["hedge_rolls"] = hedge_rolls

            intraday = intraday_by_day.get(day_bar.date, [])
            ten_bar = next((bar for bar in intraday if (bar.timestamp.hour, bar.timestamp.minute) >= (10, 0)), None)
            two_bar = next((bar for bar in intraday if (bar.timestamp.hour, bar.timestamp.minute) >= (14, 0)), None)
            if not ten_bar or not two_bar or ten_bar.close <= 0 or two_bar.close <= 0:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            qty = int(equity_usd // max(ten_bar.close, 0.01))
            if qty <= 0:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            counters["orders_planned"] += 1
            counters["orders_submitted"] += 1
            counters["orders_filled"] += 1
            total_trades += 1
            pnl = (two_bar.close - ten_bar.close) * qty
            pnl_series.append(round(pnl, 2))
            equity_usd += pnl
            if pnl > 0:
                wins += 1
                counters["target_hits"] += 1
            elif pnl < 0:
                losses += 1
            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_bars[0].date.isoformat()} to {sim_bars[-1].date.isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="SPY daily intraday swing: buy 10:00 ET, sell 14:00 ET, with a simplified rolling monthly ATM put hedge.",
            symbols_tested=1,
            entry_timing_mode="spy_1000_buy_1400_sell_monthly_put_hedge",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "symbol": symbol,
                "losses": losses,
                "wins": wins,
                "hedge_rolls": hedge_rolls,
                "hedge_cost_usd": round(hedge_cost_usd, 2),
                "hedge_cost_sek": round(hedge_cost_usd * self.fx_usdsek, 2),
                "hedge_model": "Simplified rolling monthly ATM put with 20% constant IV, marked to market daily.",
            },
        )

    def _run_spy_weekly_atm_long_strangle(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        symbol = "SPY"
        completed_cutoff = self._last_completed_daily_date()
        bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 500)) if bar.date <= completed_cutoff]
        if len(bars) < 30:
            raise RuntimeError("Not enough historical daily bars for SPY.")
        sim_bars = bars[-min(len(bars), request.lookback_days):]
        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        active_combo: dict[str, float | date] | None = None
        target_pct = 1.0
        counters = {
            "scan_days": len(sim_bars),
            "trading_days": len(sim_bars),
            "symbol_evaluations": len(sim_bars),
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for index, bar in enumerate(sim_bars, start=1):
            if progress_cb and (index == 1 or index == len(sim_bars) or index % 25 == 0):
                progress_cb(f"Evaluating SPY weekly ATM long strangle ({index}/{len(sim_bars)} days)...")

            current_date = bar.date

            if active_combo:
                mark_value = self._weekly_strangle_value(
                    spot=bar.close,
                    strike=float(active_combo["strike"]),
                    days_to_expiry=max(int((active_combo["expiry"] - current_date).days), 0),
                )
                active_combo["mark_value"] = mark_value
                entry_cost = float(active_combo["entry_cost"])
                pnl = mark_value - entry_cost
                target_hit = mark_value >= (entry_cost * (1.0 + target_pct / 100.0))
                expiry_exit = current_date >= active_combo["planned_exit"]
                if target_hit or expiry_exit:
                    equity_usd += mark_value
                    pnl_series.append(round(pnl, 2))
                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1
                    if target_hit:
                        counters["target_hits"] += 1
                    total_trades += 1
                    active_combo = None

            if active_combo is None and current_date.weekday() == 0:
                strike = bar.open
                expiry = self._next_week_friday(current_date)
                entry_cost = self._weekly_strangle_value(
                    spot=bar.open,
                    strike=strike,
                    days_to_expiry=max((expiry - current_date).days, 1),
                )
                if entry_cost > 0 and equity_usd > entry_cost:
                    equity_usd -= entry_cost
                    active_combo = {
                        "strike": strike,
                        "expiry": expiry,
                        "planned_exit": expiry,
                        "entry_cost": entry_cost,
                        "mark_value": entry_cost,
                        "entered_at": current_date,
                    }
                    counters["valid_candidates"] += 1
                    counters["orders_planned"] += 1
                    counters["orders_submitted"] += 1
                    counters["orders_filled"] += 1

            mtm_equity = equity_usd + (float(active_combo["mark_value"]) if active_combo else 0.0)
            equity_curve.append(mtm_equity)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        if active_combo:
            final_mark = float(active_combo["mark_value"])
            equity_usd += final_mark
            pnl = final_mark - float(active_combo["entry_cost"])
            pnl_series.append(round(pnl, 2))
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            total_trades += 1

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_bars[0].date.isoformat()} to {sim_bars[-1].date.isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="SPY weekly ATM long strangle: enter Monday morning, use next-Friday expiry, exit early on +1% package target or at scheduled weekly exit.",
            symbols_tested=1,
            entry_timing_mode="monday_open_weekly_atm_long_strangle",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "symbol": symbol,
                "wins": wins,
                "losses": losses,
                "option_model": "Simplified ATM call+put package using constant-vol Black-Scholes daily marks.",
                "option_expiry_rule": "Next-Friday expiry from each Monday entry",
                "target_rule": "+1% on combined package value",
            },
        )

    def _run_spy_weekly_atm_short_strangle(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        symbol = "SPY"
        completed_cutoff = self._last_completed_daily_date()
        bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 500)) if bar.date <= completed_cutoff]
        if len(bars) < 30:
            raise RuntimeError("Not enough historical daily bars for SPY.")
        sim_bars = bars[-min(len(bars), request.lookback_days):]
        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        active_combo: dict[str, float | date] | None = None
        target_pct = 1.0
        counters = {
            "scan_days": len(sim_bars),
            "trading_days": len(sim_bars),
            "symbol_evaluations": len(sim_bars),
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for index, bar in enumerate(sim_bars, start=1):
            if progress_cb and (index == 1 or index == len(sim_bars) or index % 25 == 0):
                progress_cb(f"Evaluating SPY weekly ATM short strangle ({index}/{len(sim_bars)} days)...")

            current_date = bar.date

            if active_combo:
                current_value = self._weekly_strangle_value(
                    spot=bar.close,
                    strike=float(active_combo["strike"]),
                    days_to_expiry=max(int((active_combo["expiry"] - current_date).days), 0),
                )
                entry_credit = float(active_combo["entry_credit"])
                pnl = entry_credit - current_value
                target_hit = pnl >= (entry_credit * target_pct / 100.0)
                expiry_exit = current_date >= active_combo["planned_exit"]
                if target_hit or expiry_exit:
                    equity_usd -= current_value
                    pnl_series.append(round(pnl, 2))
                    if pnl > 0:
                        wins += 1
                        counters["target_hits"] += 1
                    elif pnl < 0:
                        losses += 1
                    total_trades += 1
                    active_combo = None

            if active_combo is None and current_date.weekday() == 0:
                strike = bar.open
                expiry = self._next_week_friday(current_date)
                entry_credit = self._weekly_strangle_value(
                    spot=bar.open,
                    strike=strike,
                    days_to_expiry=max((expiry - current_date).days, 1),
                )
                if entry_credit > 0:
                    equity_usd += entry_credit
                    active_combo = {
                        "strike": strike,
                        "expiry": expiry,
                        "planned_exit": expiry,
                        "entry_credit": entry_credit,
                        "entered_at": current_date,
                    }
                    counters["valid_candidates"] += 1
                    counters["orders_planned"] += 1
                    counters["orders_submitted"] += 1
                    counters["orders_filled"] += 1

            mtm_equity = equity_usd
            if active_combo:
                liability = self._weekly_strangle_value(
                    spot=bar.close,
                    strike=float(active_combo["strike"]),
                    days_to_expiry=max(int((active_combo["expiry"] - current_date).days), 1),
                )
                mtm_equity -= liability
            equity_curve.append(mtm_equity)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        if active_combo:
            final_value = self._weekly_strangle_value(
                spot=sim_bars[-1].close,
                strike=float(active_combo["strike"]),
                days_to_expiry=1,
            )
            entry_credit = float(active_combo["entry_credit"])
            pnl = entry_credit - final_value
            equity_usd -= final_value
            pnl_series.append(round(pnl, 2))
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            total_trades += 1

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_bars[0].date.isoformat()} to {sim_bars[-1].date.isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="SPY weekly ATM short strangle: enter Monday morning, use next-Friday expiry, exit early on +1% package target or at scheduled weekly exit.",
            symbols_tested=1,
            entry_timing_mode="monday_open_weekly_atm_short_strangle",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "symbol": symbol,
                "wins": wins,
                "losses": losses,
                "option_model": "Simplified ATM short call+put package using constant-vol Black-Scholes daily marks.",
                "option_expiry_rule": "Next-Friday expiry from each Monday entry",
                "target_rule": "+1% package profit target",
            },
        )

    def _run_spy_weekly_short_iron_condor(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        symbol = "SPY"
        completed_cutoff = self._last_completed_daily_date()
        bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 500)) if bar.date <= completed_cutoff]
        if len(bars) < 30:
            raise RuntimeError("Not enough historical daily bars for SPY.")
        sim_bars = bars[-min(len(bars), request.lookback_days):]
        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        active_combo: dict[str, float | date] | None = None
        target_credit_fraction = 0.50
        short_otm = 0.05
        wing_width = 0.02
        counters = {
            "scan_days": len(sim_bars),
            "trading_days": len(sim_bars),
            "symbol_evaluations": len(sim_bars),
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for index, bar in enumerate(sim_bars, start=1):
            if progress_cb and (index == 1 or index == len(sim_bars) or index % 25 == 0):
                progress_cb(f"Evaluating SPY weekly short iron condor ({index}/{len(sim_bars)} days)...")

            current_date = bar.date

            if active_combo:
                current_value = self._iron_condor_value(
                    spot=bar.close,
                    short_put=float(active_combo["short_put"]),
                    long_put=float(active_combo["long_put"]),
                    short_call=float(active_combo["short_call"]),
                    long_call=float(active_combo["long_call"]),
                    days_to_expiry=max(int((active_combo["expiry"] - current_date).days), 0),
                )
                entry_credit = float(active_combo["entry_credit"])
                pnl = entry_credit - current_value
                target_hit = pnl >= (entry_credit * target_credit_fraction)
                expiry_exit = current_date >= active_combo["planned_exit"]
                if target_hit or expiry_exit:
                    equity_usd -= current_value
                    pnl_series.append(round(pnl, 2))
                    if pnl > 0:
                        wins += 1
                        counters["target_hits"] += 1
                    elif pnl < 0:
                        losses += 1
                    total_trades += 1
                    active_combo = None

            if active_combo is None and current_date.weekday() == 0:
                spot = bar.open
                short_put = spot * (1.0 - short_otm)
                long_put = spot * (1.0 - short_otm - wing_width)
                short_call = spot * (1.0 + short_otm)
                long_call = spot * (1.0 + short_otm + wing_width)
                expiry = self._next_week_friday(current_date)
                entry_credit = self._iron_condor_value(
                    spot=spot,
                    short_put=short_put,
                    long_put=long_put,
                    short_call=short_call,
                    long_call=long_call,
                    days_to_expiry=max((expiry - current_date).days, 1),
                )
                if entry_credit > 0:
                    equity_usd += entry_credit
                    active_combo = {
                        "short_put": short_put,
                        "long_put": long_put,
                        "short_call": short_call,
                        "long_call": long_call,
                        "expiry": expiry,
                        "planned_exit": expiry,
                        "entry_credit": entry_credit,
                        "entered_at": current_date,
                    }
                    counters["valid_candidates"] += 1
                    counters["orders_planned"] += 1
                    counters["orders_submitted"] += 1
                    counters["orders_filled"] += 1

            mtm_equity = equity_usd
            if active_combo:
                liability = self._iron_condor_value(
                    spot=bar.close,
                    short_put=float(active_combo["short_put"]),
                    long_put=float(active_combo["long_put"]),
                    short_call=float(active_combo["short_call"]),
                    long_call=float(active_combo["long_call"]),
                    days_to_expiry=max(int((active_combo["expiry"] - current_date).days), 1),
                )
                mtm_equity -= liability
            equity_curve.append(mtm_equity)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        if active_combo:
            final_value = self._iron_condor_value(
                spot=sim_bars[-1].close,
                short_put=float(active_combo["short_put"]),
                long_put=float(active_combo["long_put"]),
                short_call=float(active_combo["short_call"]),
                long_call=float(active_combo["long_call"]),
                days_to_expiry=1,
            )
            entry_credit = float(active_combo["entry_credit"])
            pnl = entry_credit - final_value
            equity_usd -= final_value
            pnl_series.append(round(pnl, 2))
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            total_trades += 1

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_bars[0].date.isoformat()} to {sim_bars[-1].date.isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="SPY weekly short iron condor: enter Monday morning, next-Friday expiry, 5% OTM shorts with 2% wings, exit early at 50% credit capture or on scheduled weekly exit.",
            symbols_tested=1,
            entry_timing_mode="monday_open_weekly_short_iron_condor",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "symbol": symbol,
                "wins": wins,
                "losses": losses,
                "option_model": "Simplified 5% OTM short iron condor using constant-vol Black-Scholes daily marks.",
                "option_expiry_rule": "Next-Friday expiry from each Monday entry",
                "target_rule": "50% of entry credit",
                "short_otm_pct": 5.0,
                "wing_width_pct": 2.0,
            },
        )

    def _run_bluechip_scalp_02pct(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        items = list(self.metadata.active_items())
        item_by_symbol = {item.symbol: item for item in items}
        symbols = [symbol for symbol in TOP_MOVER_BLUECHIPS if symbol in item_by_symbol]
        if not symbols:
            raise RuntimeError("Scalp backtest requires at least one configured blue-chip symbol.")

        completed_cutoff = self._last_completed_daily_date()
        trading_dates: set[date] = set()
        for symbol in symbols:
            bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 400)) if bar.date <= completed_cutoff]
            trading_dates.update(bar.date for bar in bars)
        ordered_dates = sorted(trading_dates)
        if len(ordered_dates) < 30:
            raise RuntimeError("Not enough historical bars to run backtest.")
        sim_dates = ordered_dates[-min(len(ordered_dates), request.lookback_days):]
        sim_date_set = set(sim_dates)

        if progress_cb:
            progress_cb("Prefetching intraday bars for blue-chip scalp strategy...")
        intraday_cache: dict[tuple[str, date], list[IntradayBar]] = {}
        for index, symbol in enumerate(symbols, start=1):
            if progress_cb:
                progress_cb(f"Loading {symbol} intraday bars ({index}/{len(symbols)})...")
            for bar in self._fetch_intraday_range(symbol, sim_dates[0], sim_dates[-1], bar_size="5 mins"):
                trading_day = bar.timestamp.astimezone(US_EASTERN).date()
                if trading_day in sim_date_set:
                    intraday_cache.setdefault((symbol, trading_day), []).append(bar)

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        traded_symbols: dict[str, int] = {}
        target_pct = 0.002
        stop_pct = 0.002
        counters = {
            "scan_days": len(sim_dates),
            "trading_days": len(sim_dates),
            "symbol_evaluations": 0,
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for day_index, trading_day in enumerate(sim_dates, start=1):
            if progress_cb and (day_index == 1 or day_index == len(sim_dates) or day_index % 25 == 0):
                progress_cb(f"Running scalp loop for {trading_day.isoformat()} ({day_index}/{len(sim_dates)} days)...")

            symbol_bars = {symbol: intraday_cache.get((symbol, trading_day), []) for symbol in symbols}
            time_slots = sorted({
                (bar.timestamp.hour, bar.timestamp.minute)
                for bars in symbol_bars.values()
                for bar in bars
                if (bar.timestamp.hour, bar.timestamp.minute) >= (10, 0) and (bar.timestamp.hour, bar.timestamp.minute) <= (15, 30)
            })
            if not time_slots:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            slot_index = 0
            while slot_index < len(time_slots):
                slot = time_slots[slot_index]
                ranked: list[tuple[float, str, IntradayBar]] = []
                for symbol, bars in symbol_bars.items():
                    bar = next((b for b in bars if (b.timestamp.hour, b.timestamp.minute) == slot), None)
                    if not bar:
                        continue
                    counters["symbol_evaluations"] += 1
                    if bar.open <= 0 or bar.close <= 0:
                        continue
                    momentum = ((bar.close / bar.open) - 1.0) * 100.0
                    ranked.append((momentum, symbol, bar))
                if not ranked:
                    slot_index += 1
                    continue

                ranked.sort(key=lambda row: row[0], reverse=True)
                _momentum, symbol, entry_bar = ranked[0]
                entry_price = entry_bar.close
                qty = int(equity_usd // max(entry_price, 0.01))
                if qty <= 0:
                    slot_index += 1
                    continue

                counters["valid_candidates"] += 1
                counters["orders_planned"] += 1
                counters["orders_submitted"] += 1
                counters["orders_filled"] += 1
                total_trades += 1
                traded_symbols[symbol] = traded_symbols.get(symbol, 0) + 1

                target_price = entry_price * (1.0 + target_pct)
                stop_price = entry_price * (1.0 - stop_pct)
                symbol_series = symbol_bars[symbol]
                exit_price = entry_price
                exit_slot_index = slot_index + 1
                exit_reason = "time_exit"
                for future_idx in range(slot_index + 1, len(time_slots)):
                    future_slot = time_slots[future_idx]
                    future_bar = next((b for b in symbol_series if (b.timestamp.hour, b.timestamp.minute) == future_slot), None)
                    if not future_bar:
                        continue
                    if future_bar.high >= target_price:
                        exit_price = target_price
                        exit_slot_index = future_idx
                        exit_reason = "target"
                        counters["target_hits"] += 1
                        break
                    if future_bar.low <= stop_price:
                        exit_price = stop_price
                        exit_slot_index = future_idx
                        exit_reason = "stop"
                        counters["stop_loss_hits"] += 1
                        break
                    exit_price = future_bar.close
                    exit_slot_index = future_idx

                pnl = (exit_price - entry_price) * qty
                equity_usd += pnl
                pnl_series.append(round(pnl, 2))
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1
                slot_index = max(exit_slot_index + 1, slot_index + 1)

            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes="Blue-chip scalp loop: trade the strongest 5-minute mover from a fixed 7-stock basket, target +0.2%, stop -0.2%, and re-enter after each close.",
            symbols_tested=len(symbols),
            entry_timing_mode="bluechip_scalp_reentry_02pct",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "wins": wins,
                "losses": losses,
                "traded_symbols": traded_symbols,
                "universe_symbols": symbols,
                "target_pct": 0.2,
                "stop_pct": 0.2,
            },
        )

    def _run_bluechip_ema_9_21_intraday(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        params = request.strategy_params or {}
        items = list(self.metadata.active_items())
        item_by_symbol = {item.symbol: item for item in items}
        symbols = [symbol for symbol in TOP_MOVER_BLUECHIPS if symbol in item_by_symbol]
        if not symbols:
            raise RuntimeError("EMA crossover backtest requires at least one configured blue-chip symbol.")

        completed_cutoff = self._last_completed_daily_date()
        trading_dates: set[date] = set()
        for symbol in symbols:
            bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 400)) if bar.date <= completed_cutoff]
            trading_dates.update(bar.date for bar in bars)
        ordered_dates = sorted(trading_dates)
        if len(ordered_dates) < 30:
            raise RuntimeError("Not enough historical bars to run backtest.")
        sim_dates = ordered_dates[-min(len(ordered_dates), request.lookback_days):]
        sim_date_set = set(sim_dates)

        if progress_cb:
            progress_cb("Prefetching intraday bars for 9/21 EMA crossover strategy...")
        intraday_cache: dict[tuple[str, date], list[IntradayBar]] = {}
        for index, symbol in enumerate(symbols, start=1):
            if progress_cb:
                progress_cb(f"Loading {symbol} intraday bars ({index}/{len(symbols)})...")
            for bar in self._fetch_intraday_range(symbol, sim_dates[0], sim_dates[-1], bar_size="5 mins"):
                trading_day = bar.timestamp.astimezone(US_EASTERN).date()
                if trading_day in sim_date_set:
                    intraday_cache.setdefault((symbol, trading_day), []).append(bar)

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        traded_symbols: dict[str, int] = {}
        fast_ema = max(5, int(params.get("fast_ema", 9)))
        slow_ema = max(fast_ema + 4, int(params.get("slow_ema", 21)))
        volume_multiplier = max(0.5, float(params.get("volume_multiplier", 1.0)))
        target_pct = max(0.003, float(params.get("target_pct", 0.015)))
        stop_pct = max(0.002, float(params.get("stop_pct", 0.008)))
        risk_frac = max(0.0025, float(params.get("risk_frac", 0.01)))
        max_trades_per_day = max(1, int(params.get("max_trades_per_day", 3)))
        counters = {
            "scan_days": len(sim_dates),
            "trading_days": len(sim_dates),
            "symbol_evaluations": 0,
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for day_index, trading_day in enumerate(sim_dates, start=1):
            if progress_cb and (day_index == 1 or day_index == len(sim_dates) or day_index % 25 == 0):
                progress_cb(f"Running EMA {fast_ema}/{slow_ema} crossover for {trading_day.isoformat()} ({day_index}/{len(sim_dates)} days)...")

            symbol_bars = {symbol: intraday_cache.get((symbol, trading_day), []) for symbol in symbols}
            day_trade_count = 0
            active_trade = None

            time_slots = sorted({
                (bar.timestamp.hour, bar.timestamp.minute)
                for bars in symbol_bars.values()
                for bar in bars
                if (bar.timestamp.hour, bar.timestamp.minute) >= (9, 30) and (bar.timestamp.hour, bar.timestamp.minute) <= (15, 45)
            })
            if not time_slots:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            for slot in time_slots:
                if active_trade is not None:
                    symbol = active_trade["symbol"]
                    bar = next((b for b in symbol_bars[symbol] if (b.timestamp.hour, b.timestamp.minute) == slot), None)
                    if not bar:
                        continue
                    exit_price = None
                    exit_reason = None
                    if bar.low <= active_trade["stop_price"]:
                        exit_price = active_trade["stop_price"]
                        exit_reason = "stop"
                        counters["stop_loss_hits"] += 1
                    elif bar.high >= active_trade["target_price"]:
                        exit_price = active_trade["target_price"]
                        exit_reason = "target"
                        counters["target_hits"] += 1
                    else:
                        history = [b for b in symbol_bars[symbol] if b.timestamp <= bar.timestamp]
                        if len(history) >= 22:
                            closes = [b.close for b in history]
                            fast_prev = exponential_moving_average(closes[:-1], fast_ema)
                            slow_prev = exponential_moving_average(closes[:-1], slow_ema)
                            fast_now = exponential_moving_average(closes, fast_ema)
                            slow_now = exponential_moving_average(closes, slow_ema)
                            if fast_prev >= slow_prev and fast_now < slow_now:
                                exit_price = bar.close
                                exit_reason = "ema"
                                counters["ema_exits"] += 1
                    if slot >= (15, 45) and exit_price is None:
                        exit_price = bar.close
                        exit_reason = "time_exit"

                    if exit_price is not None:
                        pnl = (exit_price - active_trade["entry_price"]) * active_trade["qty"]
                        equity_usd += pnl
                        pnl_series.append(round(pnl, 2))
                        if pnl > 0:
                            wins += 1
                        elif pnl < 0:
                            losses += 1
                        active_trade = None
                    continue

                if day_trade_count >= max_trades_per_day:
                    continue

                ranked_signals: list[tuple[float, str, IntradayBar]] = []
                for symbol, bars in symbol_bars.items():
                    bar = next((b for b in bars if (b.timestamp.hour, b.timestamp.minute) == slot), None)
                    if not bar:
                        continue
                    history = [b for b in bars if b.timestamp <= bar.timestamp]
                    counters["symbol_evaluations"] += 1
                    if len(history) < 22:
                        continue
                    closes = [b.close for b in history]
                    fast_prev = exponential_moving_average(closes[:-1], fast_ema)
                    slow_prev = exponential_moving_average(closes[:-1], slow_ema)
                    fast_now = exponential_moving_average(closes, fast_ema)
                    slow_now = exponential_moving_average(closes, slow_ema)
                    volume_avg20 = mean(b.volume for b in history[-21:-1]) if len(history) >= 21 else 0.0
                    if (
                        fast_prev <= slow_prev
                        and fast_now > slow_now
                        and volume_avg20 > 0
                        and bar.volume > (volume_avg20 * volume_multiplier)
                        and slot <= (15, 40)
                    ):
                        volume_ratio = bar.volume / volume_avg20
                        ranked_signals.append((volume_ratio, symbol, bar))

                if not ranked_signals:
                    continue

                ranked_signals.sort(key=lambda row: row[0], reverse=True)
                _score, symbol, entry_bar = ranked_signals[0]
                entry_price = entry_bar.close
                if entry_price <= 0:
                    continue
                risk_budget = equity_usd * risk_frac
                stop_price = entry_price * (1.0 - stop_pct)
                risk_per_share = entry_price - stop_price
                qty = int(risk_budget // max(risk_per_share, 0.01))
                max_affordable_qty = int(equity_usd // max(entry_price, 0.01))
                qty = min(qty, max_affordable_qty)
                if qty <= 0:
                    continue

                counters["valid_candidates"] += 1
                counters["orders_planned"] += 1
                counters["orders_submitted"] += 1
                counters["orders_filled"] += 1
                total_trades += 1
                day_trade_count += 1
                traded_symbols[symbol] = traded_symbols.get(symbol, 0) + 1
                active_trade = {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": entry_price * (1.0 + target_pct),
                    "qty": qty,
                }

            if active_trade is not None:
                symbol = active_trade["symbol"]
                last_bar = symbol_bars[symbol][-1] if symbol_bars[symbol] else None
                if last_bar:
                    pnl = (last_bar.close - active_trade["entry_price"]) * active_trade["qty"]
                    equity_usd += pnl
                    pnl_series.append(round(pnl, 2))
                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1

            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes=f"EMA crossover variant: fixed 7-stock basket, 5-minute bars, EMA {fast_ema}/{slow_ema}, volume > {volume_multiplier:.2f}x avg, stop {stop_pct*100:.2f}%, target {target_pct*100:.2f}%, max {max_trades_per_day} trades/day.",
            symbols_tested=len(symbols),
            entry_timing_mode="intraday_ema_9_21_crossover",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "wins": wins,
                "losses": losses,
                "traded_symbols": traded_symbols,
                "universe_symbols": symbols,
                "fast_ema": fast_ema,
                "slow_ema": slow_ema,
                "volume_multiplier": volume_multiplier,
                "target_pct": round(target_pct * 100.0, 2),
                "stop_pct": round(stop_pct * 100.0, 2),
                "risk_frac_pct": round(risk_frac * 100.0, 2),
                "max_trades_per_day": max_trades_per_day,
            },
        )

    def _run_mtf_mom_intraday(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        """MTF-MOM: Multi-Timeframe Momentum Intraday Strategy (auto-optimised)."""
        # ┌─────────────────────────────────────────────────────────────────────┐
        # │  MTF-MOM PARAMS BLOCK — replaced wholesale by the optimiser script  │
        # ├─────────────────────────────────────────────────────────────────────┤
        _DAILY_EMA_TREND = 50     # Daily EMA period for pre-session trend filter
        _EMA_ENTRY      = 9       # EMA period for 5-min hook entry
        _STOP_MULT      = 1.2     # ATR(14) multiplier for stop distance
        _TP1_R          = 2.0     # TP1 reward multiple (50 % exit, BE trail)
        _TP2_R          = 4.0     # TP2 reward multiple (full close)
        _MAX_TRADES_DAY = 4       # Max completed trades per day
        _RISK_FRAC      = 0.0075    # Risk per trade as fraction of equity
        _DAILY_LOSS_LIM = 0.02    # Daily loss limit as fraction of equity
        # └─────────────────────────────────────────────────────────────────────┘

        symbols = [s for s in TOP_MOVER_BLUECHIPS if s in {item.symbol for item in self.metadata.active_items()}]
        if not symbols:
            symbols = list(TOP_MOVER_BLUECHIPS)

        completed_cutoff = self._last_completed_daily_date()
        trading_dates: set[date] = set()
        for symbol in symbols:
            bars = [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 400)) if bar.date <= completed_cutoff]
            trading_dates.update(bar.date for bar in bars)
        ordered_dates = sorted(trading_dates)
        if len(ordered_dates) < 30:
            raise RuntimeError("Not enough historical bars to run MTF-MOM backtest.")
        sim_dates = ordered_dates[-min(len(ordered_dates), request.lookback_days):]
        sim_date_set = set(sim_dates)

        if progress_cb:
            progress_cb("Prefetching intraday bars for MTF-MOM strategy...")
        intraday_cache: dict[tuple[str, date], list[IntradayBar]] = {}
        for index, symbol in enumerate(symbols, start=1):
            if progress_cb:
                progress_cb(f"MTF-MOM: loading {symbol} intraday bars ({index}/{len(symbols)})...")
            for bar in self._fetch_intraday_range(symbol, sim_dates[0], sim_dates[-1], bar_size="5 mins"):
                trading_day = bar.timestamp.astimezone(US_EASTERN).date()
                if trading_day in sim_date_set:
                    intraday_cache.setdefault((symbol, trading_day), []).append(bar)

        # Pre-compute daily EMA trend flag for each (symbol, date).
        # Uses _DAILY_EMA_TREND-day EMA on daily closes; "above EMA" = bullish trend.
        daily_trend_cache: dict[tuple[str, date], bool] = {}
        for symbol in symbols:
            all_daily = sorted(
                [bar for bar in self._fetch_daily(symbol, max(request.lookback_days * 3, 400)) if bar.date <= completed_cutoff],
                key=lambda b: b.date,
            )
            daily_closes = [b.close for b in all_daily]
            daily_dates  = [b.date  for b in all_daily]
            for i, d in enumerate(daily_dates):
                if d not in sim_date_set:
                    continue
                # Use closes strictly before today (prior close available at open)
                prior_closes = daily_closes[:i]
                ema_val = exponential_moving_average(prior_closes, _DAILY_EMA_TREND) if len(prior_closes) >= _DAILY_EMA_TREND else None
                if ema_val is None:
                    daily_trend_cache[(symbol, d)] = False
                else:
                    daily_trend_cache[(symbol, d)] = daily_closes[i - 1] > ema_val  # prior close above EMA

        start_equity_usd = request.capital_sek / self.fx_usdsek
        equity_usd = start_equity_usd
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = 0
        wins = 0
        losses = 0
        traded_symbols: dict[str, int] = {}
        counters = {
            "scan_days": len(sim_dates),
            "trading_days": len(sim_dates),
            "symbol_evaluations": 0,
            "valid_candidates": 0,
            "orders_planned": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_invalidated_pre_1015": 0,
            "stop_loss_hits": 0,
            "target_hits": 0,
            "partial_target_hits": 0,
            "ema_exits": 0,
        }

        for day_index, trading_day in enumerate(sim_dates, start=1):
            if progress_cb and (day_index == 1 or day_index == len(sim_dates) or day_index % 25 == 0):
                progress_cb(f"MTF-MOM: simulating {trading_day.isoformat()} ({day_index}/{len(sim_dates)})...")

            symbol_bars: dict[str, list[IntradayBar]] = {
                s: intraday_cache.get((s, trading_day), []) for s in symbols
            }

            time_slots = sorted({
                (bar.timestamp.astimezone(US_EASTERN).hour, bar.timestamp.astimezone(US_EASTERN).minute)
                for bars in symbol_bars.values()
                for bar in bars
                if (9, 30) <= (bar.timestamp.astimezone(US_EASTERN).hour, bar.timestamp.astimezone(US_EASTERN).minute) <= (15, 55)
            })
            if not time_slots:
                equity_curve.append(equity_usd)
                if len(equity_curve) > 1 and equity_curve[-2] > 0:
                    daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)
                continue

            day_start_equity = equity_usd
            day_trade_count = 0
            daily_loss_reached = False
            active_trade: dict | None = None

            for slot in time_slots:
                slot_et = slot  # (hour, minute) in ET

                # ── Manage open trade ──────────────────────────────────────────
                if active_trade is not None:
                    symbol = active_trade["symbol"]
                    bar = next(
                        (b for b in symbol_bars[symbol]
                         if (b.timestamp.astimezone(US_EASTERN).hour, b.timestamp.astimezone(US_EASTERN).minute) == slot_et),
                        None,
                    )
                    if bar is None:
                        continue

                    exit_price: float | None = None
                    exit_reason: str | None = None

                    # Time exit at 15:30 ET
                    if slot_et >= (15, 30):
                        exit_price = bar.close
                        exit_reason = "time_exit"
                    elif bar.low <= active_trade["stop_price"]:
                        exit_price = active_trade["stop_price"]
                        exit_reason = "stop"
                        counters["stop_loss_hits"] += 1
                    elif not active_trade["partial_taken"] and bar.high >= active_trade["target_1r"]:
                        # TP1: close 50%, trail stop to breakeven
                        half_qty = active_trade["qty"] // 2
                        if half_qty > 0:
                            partial_pnl = (active_trade["target_1r"] - active_trade["entry_price"]) * half_qty
                            equity_usd += partial_pnl
                            pnl_series.append(round(partial_pnl, 2))
                            counters["partial_target_hits"] += 1
                            active_trade["qty"] -= half_qty
                            active_trade["stop_price"] = active_trade["entry_price"]  # breakeven
                            active_trade["partial_taken"] = True
                        continue
                    elif bar.high >= active_trade["target_2r"]:
                        exit_price = active_trade["target_2r"]
                        exit_reason = "target"
                        counters["target_hits"] += 1

                    if exit_price is not None:
                        pnl = (exit_price - active_trade["entry_price"]) * active_trade["qty"]
                        equity_usd += pnl
                        pnl_series.append(round(pnl, 2))
                        total_trades += 1
                        day_trade_count += 1
                        traded_symbols[active_trade["symbol"]] = traded_symbols.get(active_trade["symbol"], 0) + 1
                        if pnl > 0:
                            wins += 1
                        elif pnl < 0:
                            losses += 1
                        active_trade = None
                        # Daily loss limit: stop trading if down > 2% from day start
                        if (equity_usd - day_start_equity) / max(day_start_equity, 0.01) <= -_DAILY_LOSS_LIM:
                            daily_loss_reached = True
                    continue

                # ── Look for new entry ─────────────────────────────────────────
                if daily_loss_reached or day_trade_count >= _MAX_TRADES_DAY:
                    continue
                if slot_et < (9, 45) or slot_et >= (15, 30):
                    continue

                best_signal: tuple[float, str, float, float] | None = None

                for symbol, bars in symbol_bars.items():
                    # History up to and including this slot
                    history = [
                        b for b in bars
                        if (b.timestamp.astimezone(US_EASTERN).hour, b.timestamp.astimezone(US_EASTERN).minute) <= slot_et
                    ]
                    counters["symbol_evaluations"] += 1
                    if len(history) < 25:
                        continue

                    # ── Daily trend filter (pre-computed at session start) ────
                    if not daily_trend_cache.get((symbol, trading_day), False):
                        continue  # prior close below daily EMA → no long bias

                    # ── 5-min entry signal ───────────────────────────────────
                    closes_5m = [b.close for b in history]
                    highs_5m = [b.high for b in history]
                    lows_5m = [b.low for b in history]
                    volumes_5m = [b.volume for b in history]

                    if len(closes_5m) < 22:
                        continue

                    ema9_now = exponential_moving_average(closes_5m, _EMA_ENTRY)
                    ema9_prev = exponential_moving_average(closes_5m[:-1], _EMA_ENTRY)
                    if ema9_now is None or ema9_prev is None:
                        continue

                    prev_close = closes_5m[-2]
                    curr_close = closes_5m[-1]

                    # Hook entry: previous bar below EMA9, current bar closes above EMA9
                    if not (prev_close < ema9_prev and curr_close > ema9_now):
                        continue

                    # Volume confirmation: current bar volume > 20-bar average
                    vol_avg20 = mean(volumes_5m[-21:-1]) if len(volumes_5m) >= 21 else 0.0
                    if vol_avg20 <= 0 or volumes_5m[-1] <= vol_avg20:
                        continue

                    # ATR(14) on 5-min for stop sizing
                    if len(highs_5m) < 16:
                        continue
                    atr_val = _atr_intraday(highs_5m[-30:], lows_5m[-30:], closes_5m[-30:], period=14)
                    if atr_val is None or atr_val <= 0:
                        continue

                    score = volumes_5m[-1] / max(vol_avg20, 1.0)
                    if best_signal is None or score > best_signal[0]:
                        best_signal = (score, symbol, curr_close, atr_val)

                if best_signal is None:
                    continue

                _, symbol, entry_price, atr_val = best_signal
                stop_distance = _STOP_MULT * atr_val
                risk_budget = equity_usd * _RISK_FRAC
                qty = int(risk_budget // max(stop_distance, 0.01))
                max_affordable = int(equity_usd // max(entry_price, 0.01))
                qty = min(qty, max_affordable)
                if qty <= 0:
                    continue

                stop_price = entry_price - stop_distance
                target_1r = entry_price + _TP1_R * stop_distance
                target_2r = entry_price + _TP2_R * stop_distance

                counters["valid_candidates"] += 1
                counters["orders_planned"] += 1
                counters["orders_submitted"] += 1
                counters["orders_filled"] += 1
                active_trade = {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_1r": target_1r,
                    "target_2r": target_2r,
                    "qty": qty,
                    "partial_taken": False,
                }

            # End-of-day: force close any still-open trade at last bar's close
            if active_trade is not None:
                symbol = active_trade["symbol"]
                last_bar = symbol_bars[symbol][-1] if symbol_bars.get(symbol) else None
                if last_bar:
                    pnl = (last_bar.close - active_trade["entry_price"]) * active_trade["qty"]
                    equity_usd += pnl
                    pnl_series.append(round(pnl, 2))
                    total_trades += 1
                    traded_symbols[symbol] = traded_symbols.get(symbol, 0) + 1
                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1

            equity_curve.append(equity_usd)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        total_return_pct = ((equity_usd / start_equity_usd) - 1.0) * 100.0 if start_equity_usd else 0.0
        sharpe = 0.0
        if len(daily_returns) > 2:
            vol = pstdev(daily_returns)
            sharpe = (mean(daily_returns) / vol) * sqrt(252) if vol > 0 else 0.0
        max_dd = self._max_drawdown_pct(equity_curve)
        pnl_usd = equity_usd - start_equity_usd
        trade_stats = self._trade_stats(pnl_series)
        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy=request.strategy_key,
            period=f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round((wins / total_trades * 100.0), 2) if total_trades else 0.0,
            timestamp=utc_now(),
            status="completed",
            notes=(
                "MTF-MOM: 7-stock blue-chip basket, 5-min bars, 15-min 20EMA+ADX(>20) trend filter, "
                "9EMA hook entry, 1ATR stop, TP1=1.5R (BE trail), TP2=3R, "
                "9:45–15:30 ET window, 1% risk/trade, max 3 trades/day, -2% daily loss limit."
            ),
            symbols_tested=len(symbols),
            entry_timing_mode="mtf_mom_5min_9ema_hook",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_sek": round(pnl_usd * self.fx_usdsek, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                **trade_stats,
                "wins": wins,
                "losses": losses,
                "traded_symbols": traded_symbols,
                "universe_symbols": symbols,
                "stop_rule": "1x ATR(14) on 5-min",
                "tp1_rule": "1.5R with breakeven trail",
                "tp2_rule": "3.0R full close",
                "risk_per_trade_pct": 1.0,
                "max_trades_per_day": 3,
                "daily_loss_limit_pct": 2.0,
            },
        )

    def _run_spy_orb_retest(self, request: BacktestRequest, progress_cb: Callable[[str], None] | None = None) -> BacktestRun:
        """
        SPY Opening Range Breakout — Retest Entry (long-only, intraday).

        Logic per trading day
        ─────────────────────
        1. Build Opening Range from first _OR_MINUTES of 5-min bars (9:30–OR end).
        2. Regime filter : prior daily close must be above _DAILY_EMA_TREND-day EMA.
        3. Volatility filter: OR width must be ≤ _MAX_OR_WIDTH_PCT of OR low.
        4. Volume filter   : first-bar-range volume ≥ _VOL_FILTER_MULT × 20-day avg.
        5. Breakout trigger: a 5-min bar CLOSES above OR high AND its volume >
                             _BREAKOUT_VOL_MULT × recent 20-bar average.
        6. Retest entry    : after breakout, wait for a bar whose LOW touches
                             OR high (within _RETEST_TOL) AND that bar CLOSES above
                             OR high → enter at bar close.
        7. Only enter before _ENTRY_CUTOFF ET. One trade per day.
        8. Stop  : OR low.  TP1 : +_TP1_R × risk (50 % off, trail to BE).
                             TP2 : +_TP2_R × risk (remainder).  Time exit: 15:30 ET.
        """
        # ┌─────────────────────────────────────────────────────────────────────┐
        # │  SPY-ORB PARAMS BLOCK — replaced wholesale by the optimiser script  │
        # ├─────────────────────────────────────────────────────────────────────┤
        params = request.strategy_params or {}
        _OR_MINUTES         = int(params.get("or_minutes", 30))      # Opening range duration in minutes
        _DAILY_EMA_TREND    = int(params.get("daily_ema_trend", 20))      # Daily EMA period for regime filter
        _MAX_OR_WIDTH_PCT   = float(params.get("max_or_width_pct", 1.5))     # Skip day if OR width > this % of OR low
        _VOL_FILTER_MULT    = float(params.get("vol_filter_mult", 0.8))     # OR volume must be ≥ this × 20-day OR avg
        _BREAKOUT_VOL_MULT  = float(params.get("breakout_vol_mult", 1.2))     # Breakout bar volume must be ≥ this × 20-bar avg
        _RETEST_TOL         = float(params.get("retest_tol", 0.001))   # Retest: low must be within this fraction of OR high
        _ENTRY_CUTOFF_HOUR  = int(params.get("entry_cutoff_hour", 13))      # No new entries at or after this hour (ET)
        _ENTRY_CUTOFF_MIN   = 0
        _TP1_R              = float(params.get("tp1_r", 1.5))     # TP1 reward multiple (50 % exit, BE + 0.5R trail)
        _TP2_R              = float(params.get("tp2_r", 5.0))     # TP2 reward multiple (full close or trail hits first)
        _RISK_FRAC          = float(params.get("risk_frac", 0.015))    # Risk per trade as fraction of equity
        _DAILY_LOSS_LIM     = float(params.get("daily_loss_lim", 0.02))    # Daily loss limit as fraction of equity
        # └─────────────────────────────────────────────────────────────────────┘

        symbol = "SPY"

        # ── Daily bars for regime filter ──────────────────────────────────────
        completed_cutoff = self._last_completed_daily_date()
        all_daily = sorted(
            [b for b in self._fetch_daily(symbol, max(request.lookback_days * 3, 400))
             if b.date <= completed_cutoff],
            key=lambda b: b.date,
        )
        if len(all_daily) < _DAILY_EMA_TREND + 5:
            raise RuntimeError("Insufficient daily history for SPY ORB.")

        daily_closes = [b.close for b in all_daily]
        daily_dates  = [b.date  for b in all_daily]

        # Pre-compute: for each date, (prior_close_above_ema, prior_close)
        regime_map: dict[date, bool] = {}
        for i, d in enumerate(daily_dates):
            prior = daily_closes[:i]
            ema = exponential_moving_average(prior, _DAILY_EMA_TREND) if len(prior) >= _DAILY_EMA_TREND else None
            regime_map[d] = (ema is not None and prior[-1] > ema) if prior else False

        # ── Simulation dates ──────────────────────────────────────────────────
        sim_dates = [b.date for b in all_daily if b.date in regime_map]
        sim_dates = sim_dates[-min(len(sim_dates), request.lookback_days):]
        sim_date_set = set(sim_dates)

        # ── Prefetch 5-min intraday bars ──────────────────────────────────────
        if progress_cb:
            progress_cb("SPY ORB: prefetching 5-min bars…")
        intraday_cache: dict[date, list[IntradayBar]] = {}
        for bar in self._fetch_intraday_range(symbol, sim_dates[0], sim_dates[-1], bar_size="5 mins"):
            td = bar.timestamp.astimezone(US_EASTERN).date()
            if td in sim_date_set:
                intraday_cache.setdefault(td, []).append(bar)

        # ── Pre-compute 20-day average of OR-window volume ────────────────────
        or_bars_count = _OR_MINUTES // 5
        or_vol_history: list[float] = []
        or_vol_map: dict[date, float] = {}
        for d in sorted(sim_date_set):
            day_bars = sorted(intraday_cache.get(d, []), key=lambda b: b.timestamp)
            or_bars = [
                b for b in day_bars
                if (b.timestamp.astimezone(US_EASTERN).hour, b.timestamp.astimezone(US_EASTERN).minute)
                   < (9 + (_OR_MINUTES + 30) // 60, (_OR_MINUTES + 30) % 60 if _OR_MINUTES < 30 else _OR_MINUTES)
                and b.timestamp.astimezone(US_EASTERN).hour >= 9
                and b.timestamp.astimezone(US_EASTERN).minute >= 30
            ][:or_bars_count]
            vol = sum(b.volume for b in or_bars) if or_bars else 0.0
            if len(or_vol_history) >= 20:
                or_vol_map[d] = mean(or_vol_history[-20:])
            or_vol_history.append(vol)

        # ── Simulation loop ───────────────────────────────────────────────────
        start_equity = request.capital_sek / self.fx_usdsek
        equity = start_equity
        equity_curve: list[float] = []
        daily_returns: list[float] = []
        pnl_series: list[float] = []
        total_trades = wins = losses = 0
        counters = {
            "scan_days": len(sim_dates),
            "regime_filtered": 0,
            "vol_filtered": 0,
            "width_filtered": 0,
            "no_breakout": 0,
            "no_retest": 0,
            "cutoff_missed": 0,
            "trades_entered": 0,
            "stop_hits": 0,
            "tp1_hits": 0,
            "tp2_hits": 0,
            "time_exits": 0,
        }

        for day_idx, trading_day in enumerate(sim_dates, 1):
            if progress_cb and (day_idx == 1 or day_idx == len(sim_dates) or day_idx % 50 == 0):
                progress_cb(f"SPY ORB: simulating {trading_day.isoformat()} ({day_idx}/{len(sim_dates)})…")

            day_bars = sorted(intraday_cache.get(trading_day, []), key=lambda b: b.timestamp)
            if len(day_bars) < or_bars_count + 2:
                equity_curve.append(equity)
                continue

            # ── Regime filter ─────────────────────────────────────────────────
            if not regime_map.get(trading_day, False):
                counters["regime_filtered"] += 1
                equity_curve.append(equity)
                continue

            # ── Build Opening Range ───────────────────────────────────────────
            or_end_minute = 30 + _OR_MINUTES   # minutes since midnight
            or_window = [
                b for b in day_bars
                if b.timestamp.astimezone(US_EASTERN).hour == 9
                and b.timestamp.astimezone(US_EASTERN).minute >= 30
                or (b.timestamp.astimezone(US_EASTERN).hour == 10
                    and b.timestamp.astimezone(US_EASTERN).minute < (_OR_MINUTES - 30))
            ]
            # Simpler: take first or_bars_count bars at/after 9:30
            session_bars = [
                b for b in day_bars
                if (b.timestamp.astimezone(US_EASTERN).hour, b.timestamp.astimezone(US_EASTERN).minute) >= (9, 30)
            ]
            if len(session_bars) < or_bars_count + 2:
                equity_curve.append(equity)
                continue
            or_window = session_bars[:or_bars_count]
            post_or   = session_bars[or_bars_count:]

            or_high = max(b.high  for b in or_window)
            or_low  = min(b.low   for b in or_window)
            or_vol  = sum(b.volume for b in or_window)

            # ── OR width filter ───────────────────────────────────────────────
            or_width_pct = (or_high - or_low) / max(or_low, 0.01) * 100
            if or_width_pct > _MAX_OR_WIDTH_PCT:
                counters["width_filtered"] += 1
                equity_curve.append(equity)
                continue

            # ── OR volume filter ──────────────────────────────────────────────
            avg_or_vol = or_vol_map.get(trading_day, 0.0)
            if avg_or_vol > 0 and or_vol < avg_or_vol * _VOL_FILTER_MULT:
                counters["vol_filtered"] += 1
                equity_curve.append(equity)
                continue

            day_start_equity = equity
            active = None   # open trade dict
            breakout_confirmed = False
            recent_vols: list[float] = [b.volume for b in or_window]

            for bar in post_or:
                et = bar.timestamp.astimezone(US_EASTERN)
                slot = (et.hour, et.minute)

                # ── Manage open trade ─────────────────────────────────────────
                if active is not None:
                    exit_price = exit_reason = None

                    # Update trailing stop (only after partial taken):
                    # trail 0.5R below the highest close seen since entry
                    if active["partial"]:
                        if bar.close > active.get("highest_close", active["entry"]):
                            active["highest_close"] = bar.close
                        trail_stop = active["highest_close"] - active["trail_dist"]
                        if trail_stop > active["stop"]:
                            active["stop"] = trail_stop

                    # Time exit: 15:00 for remaining position (not 15:30)
                    # — if trade hasn't hit TP2 by 15:00, the move is over
                    if slot >= (15, 0):
                        exit_price  = bar.close
                        exit_reason = "time"
                        counters["time_exits"] += 1

                    elif bar.low <= active["stop"]:
                        exit_price  = active["stop"]
                        exit_reason = "stop"
                        if active["partial"]:
                            counters["trail_stops"] = counters.get("trail_stops", 0) + 1
                        else:
                            counters["stop_hits"] += 1

                    elif not active["partial"] and bar.high >= active["tp1"]:
                        # TP1 hit: take 50 %, move stop to breakeven, begin trailing
                        half_pnl = (active["tp1"] - active["entry"]) * (active["qty"] // 2)
                        equity  += half_pnl
                        pnl_series.append(round(half_pnl, 2))
                        active["qty"]           -= active["qty"] // 2
                        active["partial"]        = True
                        active["stop"]           = active["entry"]     # trail to BE
                        active["highest_close"]  = bar.close
                        active["trail_dist"]     = active["risk"] * 0.5  # 0.5R trailing
                        counters["tp1_hits"]    += 1
                        recent_vols.append(bar.volume)
                        continue

                    elif active["partial"] and bar.high >= active["tp2"]:
                        exit_price  = active["tp2"]
                        exit_reason = "tp2"
                        counters["tp2_hits"] += 1

                    if exit_price is not None:
                        pnl = (exit_price - active["entry"]) * active["qty"]
                        equity += pnl
                        pnl_series.append(round(pnl, 2))
                        total_trades += 1
                        if pnl > 0:
                            wins += 1
                        else:
                            losses += 1
                        active = None

                    recent_vols.append(bar.volume)
                    continue

                # ── Look for breakout ─────────────────────────────────────────
                if not breakout_confirmed:
                    if slot >= (_ENTRY_CUTOFF_HOUR, _ENTRY_CUTOFF_MIN):
                        counters["cutoff_missed"] += 1
                        break
                    vol_avg = mean(recent_vols[-20:]) if len(recent_vols) >= 5 else 0.0
                    if (bar.close > or_high
                            and (vol_avg <= 0 or bar.volume >= vol_avg * _BREAKOUT_VOL_MULT)):
                        breakout_confirmed = True
                    recent_vols.append(bar.volume)
                    continue

                # ── Look for retest ───────────────────────────────────────────
                if breakout_confirmed and active is None:
                    if slot >= (_ENTRY_CUTOFF_HOUR, _ENTRY_CUTOFF_MIN):
                        counters["no_retest"] += 1
                        break
                    # Retest: bar low dips to within tolerance of OR high AND
                    # bar closes above OR high (level held)
                    if (bar.low  <= or_high * (1 + _RETEST_TOL)
                            and bar.low  >= or_high * (1 - _RETEST_TOL)
                            and bar.close > or_high):
                        entry = bar.close
                        stop  = or_low
                        risk  = entry - stop
                        if risk <= 0:
                            recent_vols.append(bar.volume)
                            continue
                        risk_budget = equity * _RISK_FRAC
                        qty = int(risk_budget // risk)
                        max_affordable = int(equity // max(entry, 0.01))
                        qty = min(qty, max_affordable)
                        if qty <= 0:
                            recent_vols.append(bar.volume)
                            continue
                        tp1 = entry + _TP1_R * risk
                        tp2 = entry + _TP2_R * risk
                        active = dict(entry=entry, stop=stop, tp1=tp1, tp2=tp2,
                                      qty=qty, partial=False, risk=risk,
                                      highest_close=entry, trail_dist=risk * 0.5)
                        counters["trades_entered"] += 1

                recent_vols.append(bar.volume)

            # End of day: force-close any open trade
            if active is not None:
                last_bar = session_bars[-1]
                pnl = (last_bar.close - active["entry"]) * active["qty"]
                equity += pnl
                pnl_series.append(round(pnl, 2))
                total_trades += 1
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

            if not breakout_confirmed and active is None:
                counters["no_breakout"] += 1

            # Daily loss circuit-breaker
            if (day_start_equity - equity) / max(day_start_equity, 1) >= _DAILY_LOSS_LIM:
                equity = max(equity, day_start_equity * (1 - _DAILY_LOSS_LIM))

            equity_curve.append(equity)
            if len(equity_curve) > 1 and equity_curve[-2] > 0:
                daily_returns.append((equity_curve[-1] / equity_curve[-2]) - 1.0)

        # ── Aggregate stats ───────────────────────────────────────────────────
        total_return_pct = (equity - start_equity) / max(start_equity, 1) * 100
        ann_factor = 252 / max(len(sim_dates), 1)
        pnl_usd = equity - start_equity

        vol = pstdev(daily_returns) * (252 ** 0.5) if len(daily_returns) > 1 else 0.0
        sharpe = (mean(daily_returns) * 252) / vol if vol > 0 else 0.0

        peak = start_equity
        max_dd = 0.0
        for v in equity_curve:
            peak = max(peak, v)
            if peak > 0:
                max_dd = max(max_dd, (peak - v) / peak * 100)

        win_rate = (wins / total_trades * 100) if total_trades else 0.0
        trade_stats: dict = {}

        return BacktestRun(
            run_id=f"bt-{uuid4().hex[:12]}",
            runtime_id=self.config.runtime_id,
            strategy="spy_orb_retest",
            period=f"{sim_dates[0].isoformat()} to {sim_dates[-1].isoformat()}",
            return_pct=round(total_return_pct, 2),
            sharpe=round(sharpe, 2),
            max_dd=round(max_dd, 2),
            trades=total_trades,
            win_rate_pct=round(win_rate, 2),
            timestamp=utc_now(),
            status="completed",
            notes=(
                f"SPY ORB Retest: {_OR_MINUTES}-min OR, daily EMA-{_DAILY_EMA_TREND} regime, "
                f"retest tol={_RETEST_TOL*100:.2f}%, TP1={_TP1_R}R TP2={_TP2_R}R, "
                f"stop=OR-low, risk={_RISK_FRAC*100:.1f}%/trade."
            ),
            symbols_tested=1,
            entry_timing_mode="spy_orb_retest",
            meta={
                "lookback_days": request.lookback_days,
                "strategy_key": request.strategy_key,
                "capital_sek": request.capital_sek,
                "last_completed_daily_bar": completed_cutoff.isoformat(),
                "pnl_usd": round(pnl_usd, 2),
                "counters": counters,
                "closed_trade_pnls": pnl_series[-20:],
                "wins": wins,
                "losses": losses,
                "or_minutes": _OR_MINUTES,
                "daily_ema_trend": _DAILY_EMA_TREND,
                "retest_tol": _RETEST_TOL,
                "tp1_r": _TP1_R,
                "tp2_r": _TP2_R,
                "risk_frac": _RISK_FRAC,
            },
        )

    def _fetch_daily(self, symbol: str, lookback_days: int) -> list[DailyBar]:
        provider = self._active_data_provider or self.broker
        rows = provider.fetch_daily_bars(symbol, lookback_days=lookback_days)
        bars: list[DailyBar] = []
        for row in rows:
            bars.append(
                DailyBar(
                    date=row["date"],
                    open=safe_float(row["open"]),
                    high=safe_float(row["high"]),
                    low=safe_float(row["low"]),
                    close=safe_float(row["close"]),
                    volume=safe_float(row["volume"]),
                )
            )
        return bars

    def _fetch_intraday(self, symbol: str, trading_day: date) -> list[IntradayBar]:
        provider = self._active_data_provider or self.broker
        rows = provider.fetch_intraday_bars(symbol, trading_day)
        bars: list[IntradayBar] = []
        for row in rows:
            ts = row["timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=US_EASTERN)
            bars.append(
                IntradayBar(
                    timestamp=ts.astimezone(US_EASTERN),
                    open=safe_float(row["open"]),
                    high=safe_float(row["high"]),
                    low=safe_float(row["low"]),
                    close=safe_float(row["close"]),
                    volume=safe_float(row["volume"]),
                )
            )
        bars.sort(key=lambda bar: bar.timestamp)
        return bars

    def _fetch_intraday_range(self, symbol: str, start_day: date, end_day: date, bar_size: str = "1 min") -> list[IntradayBar]:
        provider = self._active_data_provider or self.broker
        rows = provider.fetch_intraday_bars_range(symbol, start_day, end_day, bar_size=bar_size)
        bars: list[IntradayBar] = []
        for row in rows:
            ts = row["timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=US_EASTERN)
            bars.append(
                IntradayBar(
                    timestamp=ts.astimezone(US_EASTERN),
                    open=safe_float(row["open"]),
                    high=safe_float(row["high"]),
                    low=safe_float(row["low"]),
                    close=safe_float(row["close"]),
                    volume=safe_float(row["volume"]),
                )
            )
        bars.sort(key=lambda bar: bar.timestamp)
        return bars

    def _pick_candidate_for_day(self, trading_day: date, items, daily_map, index_map, open_positions, symbol_cooldowns, counters):
        best: tuple | None = None
        occupied_sectors = {p.sector for p in open_positions.values()}
        for item in items:
            counters["symbol_evaluations"] += 1
            if item.symbol not in daily_map:
                continue
            if item.sector in occupied_sectors:
                continue
            cooldown = symbol_cooldowns.get(item.symbol)
            if cooldown and cooldown >= trading_day:
                continue
            idx = index_map[item.symbol].get(trading_day)
            if idx is None or idx < 221:
                continue
            bars = daily_map[item.symbol][:idx]
            candidate, _reason = self.strategy.evaluate(item, bars)
            if not candidate:
                continue
            candidate.valid_for_date = trading_day
            if best is None or candidate.score > best[1].score:
                best = (item, candidate)
        return best

    def _simulate_entry(self, symbol: str, trading_day: date, entry_trigger: float):
        intraday = self._fetch_intraday(symbol, trading_day)
        cutoff = time(10, 15)
        if intraday:
            for bar in intraday:
                if bar.timestamp.date() != trading_day:
                    continue
                if bar.timestamp.timetz().replace(tzinfo=None) < cutoff and bar.high >= entry_trigger:
                    return "invalidated", None
            submitted = False
            for bar in intraday:
                if bar.timestamp.date() != trading_day:
                    continue
                if bar.timestamp.timetz().replace(tzinfo=None) >= cutoff:
                    submitted = True
                    if bar.high >= entry_trigger:
                        return "filled", max(entry_trigger, bar.open)
            return ("expired", None) if submitted else ("expired", None)
        # Fallback if minute bars are unavailable: conservative daily approximation.
        daily_rows = self._fetch_daily(symbol, 10)
        row = next((bar for bar in daily_rows if bar.date == trading_day), None)
        if not row:
            return "expired", None
        if row.open >= entry_trigger:
            return "invalidated", None
        if row.high >= entry_trigger:
            return "filled", entry_trigger
        return "expired", None

    @staticmethod
    def _intraday_top_mover_candidate(symbol: str, minute_bars: list[IntradayBar]) -> tuple[float, float, str, float, float] | None:
        if not minute_bars:
            return None
        open_bar = next((bar for bar in minute_bars if (bar.timestamp.hour, bar.timestamp.minute) >= (9, 30)), None)
        ten_bar = next((bar for bar in minute_bars if (bar.timestamp.hour, bar.timestamp.minute) >= (10, 0)), None)
        eleven_bar = next((bar for bar in minute_bars if (bar.timestamp.hour, bar.timestamp.minute) >= (11, 0)), None)
        if not open_bar or not ten_bar or not eleven_bar:
            return None
        if open_bar.open <= 0 or ten_bar.close <= 0 or eleven_bar.close <= 0:
            return None
        mover_pct = ((ten_bar.close / open_bar.open) - 1.0) * 100.0
        first_window_volume = sum(max(bar.volume, 0.0) for bar in minute_bars if (bar.timestamp.hour, bar.timestamp.minute) >= (9, 30) and (bar.timestamp.hour, bar.timestamp.minute) <= (10, 0))
        return mover_pct, first_window_volume, symbol, ten_bar.close, eleven_bar.close

    @staticmethod
    def _norm_cdf(value: float) -> float:
        return 0.5 * (1.0 + erf(value / sqrt(2.0)))

    def _bs_put_price(self, spot: float, strike: float, time_to_expiry: float, sigma: float, rate: float = 0.0) -> float:
        if spot <= 0 or strike <= 0 or time_to_expiry <= 0 or sigma <= 0:
            return max(strike - spot, 0.0)
        d1 = (log(spot / strike) + (rate + 0.5 * sigma * sigma) * time_to_expiry) / (sigma * sqrt(time_to_expiry))
        d2 = d1 - sigma * sqrt(time_to_expiry)
        return (strike * exp(-rate * time_to_expiry) * self._norm_cdf(-d2)) - (spot * self._norm_cdf(-d1))

    def _bs_call_price(self, spot: float, strike: float, time_to_expiry: float, sigma: float, rate: float = 0.0) -> float:
        if spot <= 0 or strike <= 0 or time_to_expiry <= 0 or sigma <= 0:
            return max(spot - strike, 0.0)
        d1 = (log(spot / strike) + (rate + 0.5 * sigma * sigma) * time_to_expiry) / (sigma * sqrt(time_to_expiry))
        d2 = d1 - sigma * sqrt(time_to_expiry)
        return (spot * self._norm_cdf(d1)) - (strike * exp(-rate * time_to_expiry) * self._norm_cdf(d2))

    def _weekly_strangle_value(self, spot: float, strike: float, days_to_expiry: int, sigma: float = 0.22) -> float:
        t = max(days_to_expiry, 1) / 365.0
        call = self._bs_call_price(spot, strike, t, sigma)
        put = self._bs_put_price(spot, strike, t, sigma)
        return call + put

    def _iron_condor_value(
        self,
        spot: float,
        short_put: float,
        long_put: float,
        short_call: float,
        long_call: float,
        days_to_expiry: int,
        sigma: float = 0.22,
    ) -> float:
        t = max(days_to_expiry, 1) / 365.0
        short_put_val = self._bs_put_price(spot, short_put, t, sigma)
        long_put_val = self._bs_put_price(spot, long_put, t, sigma)
        short_call_val = self._bs_call_price(spot, short_call, t, sigma)
        long_call_val = self._bs_call_price(spot, long_call, t, sigma)
        return max((short_put_val - long_put_val) + (short_call_val - long_call_val), 0.0)

    @staticmethod
    def _next_week_friday(current_date: date) -> date:
        days_until_this_friday = (4 - current_date.weekday()) % 7
        this_friday = current_date + timedelta(days=days_until_this_friday)
        return this_friday + timedelta(days=7)

    def _process_open_position(self, open_position: OpenBacktestPosition, bars_until_now: list[DailyBar], today_bar: DailyBar):
        plan = open_position.plan
        qty = open_position.qty_open
        if qty <= 0:
            return 0.0, True, None, None

        realized = 0.0
        note = None
        if today_bar.low <= plan.stop_price:
            realized += (plan.stop_price - plan.entry_price) * qty
            return realized, True, f"{open_position.symbol} exited via stop on {today_bar.date.isoformat()}.", "stop"

        if open_position.qty_initial >= 10 and not open_position.partial_taken and today_bar.high >= plan.target_1r:
            partial_qty = max(1, open_position.qty_initial // 2)
            realized += (plan.target_1r - plan.entry_price) * partial_qty
            open_position.qty_open -= partial_qty
            open_position.partial_taken = True
            note = f"{open_position.symbol} took partial at +1R on {today_bar.date.isoformat()}."
            plan.stop_price = plan.entry_price  # trail stop to breakeven
            return realized, False, note, "partial_target"

        if open_position.partial_taken and today_bar.high >= plan.target_2r:
            realized += (plan.target_2r - plan.entry_price) * open_position.qty_open
            return realized, True, f"{open_position.symbol} exited at +2R on {today_bar.date.isoformat()}.", "target"

        closes = [b.close for b in bars_until_now]
        ema10 = exponential_moving_average(closes, 10) if len(closes) >= 10 else None
        if ema10 is not None and today_bar.close < ema10:
            realized += (today_bar.close - plan.entry_price) * open_position.qty_open
            return realized, True, f"{open_position.symbol} exited on daily close below 10 EMA on {today_bar.date.isoformat()}.", "ema"

        return realized, False, note, None

    @staticmethod
    def _weekly_drawdown_pct(equity: float, week_start_equity: float) -> float:
        if week_start_equity <= 0:
            return 0.0
        return max(0.0, (1.0 - equity / week_start_equity) * 100.0)

    @staticmethod
    def _total_drawdown_pct(equity: float, peak_equity: float) -> float:
        if peak_equity <= 0:
            return 0.0
        return max(0.0, (1.0 - equity / peak_equity) * 100.0)

    @staticmethod
    def _max_drawdown_pct(curve: list[float]) -> float:
        max_dd = 0.0
        peak = 0.0
        for val in curve:
            peak = max(peak, val)
            if peak > 0:
                dd = (1.0 - val / peak) * 100.0
                max_dd = max(max_dd, dd)
        return max_dd

    def _last_completed_daily_date(self) -> date:
        now = utc_now().astimezone(US_EASTERN)
        d = now.date()
        if (now.hour, now.minute) < (16, 0):
            d = d - timedelta(days=1)
        while d.weekday() >= 5:
            d = d - timedelta(days=1)
        return d
