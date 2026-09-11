from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from trading_backend.common import US_EASTERN, safe_float, utc_now
from trading_backend.models import WatchlistItem


@dataclass
class DailyBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataService:
    def __init__(self, broker: Any) -> None:
        self.broker = broker

    def is_market_open(self, now: datetime | None = None) -> bool:
        now_et = (now or utc_now()).astimezone(US_EASTERN)
        if now_et.weekday() >= 5:
            return False
        minutes = now_et.hour * 60 + now_et.minute
        return 9 * 60 + 30 <= minutes < 16 * 60

    def is_after_entry_time(self, now: datetime | None = None) -> bool:
        now_et = (now or utc_now()).astimezone(US_EASTERN)
        return (now_et.hour, now_et.minute) >= (10, 15)

    def trading_day(self, now: datetime | None = None) -> date:
        return (now or utc_now()).astimezone(US_EASTERN).date()

    def fetch_daily_bars(self, symbol: str, lookback_days: int = 260) -> list[DailyBar]:
        rows = self.broker.fetch_daily_bars(symbol, lookback_days=lookback_days)
        bars: list[DailyBar] = []
        for row in rows:
            if row.get("close", 0) <= 0 or row.get("volume", 0) <= 0:
                continue
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

    def quote_snapshot(self, symbol: str) -> dict[str, Any]:
        return self.broker.fetch_quote(symbol)

    def validate_quote(self, quote: dict[str, Any], item: WatchlistItem) -> tuple[bool, str]:
        if not quote:
            return False, "Missing quote."
        last = safe_float(quote.get("last"))
        bid = safe_float(quote.get("bid"))
        ask = safe_float(quote.get("ask"))
        timestamp = quote.get("timestamp")
        if last <= 0 or bid <= 0 or ask <= 0:
            return False, "Invalid quote price fields."
        if ask < bid:
            return False, "Abnormal inverted spread."
        spread_bps = ((ask - bid) / last) * 10000 if last else 99999
        if spread_bps > item.max_spread_bps:
            return False, f"Spread too wide ({spread_bps:.1f} bps)."
        if isinstance(timestamp, datetime):
            age = (utc_now() - timestamp).total_seconds()
            if age > 120:
                return False, "Quote is stale."
        return True, "ok"

    @staticmethod
    def days_to_earnings(item: WatchlistItem, trading_day: date) -> int | None:
        deltas = [(earnings_date - trading_day).days for earnings_date in item.earnings_dates]
        if not deltas:
            return None
        return min(deltas, key=abs)

    @staticmethod
    def within_earnings_blackout(item: WatchlistItem, trading_day: date) -> bool:
        days = MarketDataService.days_to_earnings(item, trading_day)
        return days is not None and abs(days) <= 2

    def daily_refresh_due(self, last_refresh_at: datetime | None) -> bool:
        if last_refresh_at is None:
            return True
        now_et = utc_now().astimezone(US_EASTERN)
        last_et = last_refresh_at.astimezone(US_EASTERN)
        if now_et.date() > last_et.date():
            return True
        market_close = now_et.replace(hour=16, minute=5, second=0, microsecond=0)
        if now_et >= market_close and last_et < market_close:
            return True
        return False
