from __future__ import annotations

from typing import Any

from trading_backend.common import safe_float
from trading_backend.data.market_data import DailyBar
from trading_backend.models import PositionPlan


class PositionMonitor:
    def evaluate(
        self,
        plan: PositionPlan,
        position_row: dict[str, Any] | None,
        latest_quote: dict[str, Any] | None,
        latest_daily_bars: list[DailyBar] | None,
    ) -> tuple[str | None, str]:
        if not position_row:
            return None, "No live position row."
        market_price = safe_float((latest_quote or {}).get("last"), safe_float(position_row.get("market_price")))
        if market_price <= 0:
            return None, "No valid market price."
        if market_price <= plan.stop_price:
            return "stop", "Hard protective stop breached."
        if not plan.partial_taken and plan.quantity >= 10 and market_price >= plan.target_1r:
            return "partial_1r", "Reached +1R partial target."
        if market_price >= plan.target_2r:
            return "full_2r", "Reached +2R target."
        if latest_daily_bars and len(latest_daily_bars) >= 10:
            closes = [bar.close for bar in latest_daily_bars]
            ema10 = self._ema(closes, 10)
            if ema10 and closes[-1] < ema10:
                return "ema_exit", "Daily close is below 10 EMA."
        return None, "No exit trigger."

    @staticmethod
    def _ema(values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for value in values[period:]:
            ema = ((value - ema) * multiplier) + ema
        return ema
