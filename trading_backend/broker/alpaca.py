from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from trading_backend.common import US_EASTERN


class AlpacaHistoricalDataAdapter:
    def __init__(self) -> None:
        self.api_key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY_ID")
        self.secret_key = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
        self.base_url = (os.getenv("ALPACA_DATA_URL") or "https://data.alpaca.markets/v2").rstrip("/")
        self.feed = (os.getenv("ALPACA_DATA_FEED") or "iex").strip().lower()
        if not self.api_key or not self.secret_key:
            raise RuntimeError("Alpaca API keys are missing. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

    def fetch_daily_bars(self, symbol: str, lookback_days: int = 260) -> list[dict[str, Any]]:
        end_day = datetime.now(US_EASTERN).date()
        start_day = end_day - timedelta(days=max(lookback_days, 30))
        bars = self._fetch_bars(
            symbol=symbol,
            timeframe="1Day",
            start_dt=datetime.combine(start_day, time.min, tzinfo=timezone.utc),
            end_dt=datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone.utc),
        )
        rows: list[dict[str, Any]] = []
        for bar in bars:
            ts = self._parse_timestamp(bar.get("t"))
            rows.append(
                {
                    "date": ts.astimezone(US_EASTERN).date(),
                    "open": bar.get("o", 0.0),
                    "high": bar.get("h", 0.0),
                    "low": bar.get("l", 0.0),
                    "close": bar.get("c", 0.0),
                    "volume": bar.get("v", 0.0),
                }
            )
        rows.sort(key=lambda row: row["date"])
        return rows

    def fetch_intraday_bars_range(self, symbol: str, start_day: date, end_day: date, bar_size: str = "1 min") -> list[dict[str, Any]]:
        timeframe = self._map_timeframe(bar_size)
        start_dt = datetime.combine(start_day, time(9, 30), tzinfo=US_EASTERN).astimezone(timezone.utc)
        end_dt = datetime.combine(end_day, time(16, 0), tzinfo=US_EASTERN).astimezone(timezone.utc)
        bars = self._fetch_bars(symbol=symbol, timeframe=timeframe, start_dt=start_dt, end_dt=end_dt)
        rows: list[dict[str, Any]] = []
        for bar in bars:
            ts = self._parse_timestamp(bar.get("t"))
            rows.append(
                {
                    "timestamp": ts,
                    "open": bar.get("o", 0.0),
                    "high": bar.get("h", 0.0),
                    "low": bar.get("l", 0.0),
                    "close": bar.get("c", 0.0),
                    "volume": bar.get("v", 0.0),
                }
            )
        rows.sort(key=lambda row: row["timestamp"])
        return rows

    def fetch_intraday_bars(self, symbol: str, trading_day: date) -> list[dict[str, Any]]:
        return self.fetch_intraday_bars_range(symbol, trading_day, trading_day, bar_size="1 min")

    def _fetch_bars(self, symbol: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> list[dict[str, Any]]:
        path = f"/stocks/{symbol}/bars"
        params = {
            "timeframe": timeframe,
            "start": start_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "end": end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "adjustment": "raw",
            "feed": self.feed,
            "limit": 10000,
            "sort": "asc",
        }
        rows: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request_params = dict(params)
            if page_token:
                request_params["page_token"] = page_token
            payload = self._request_json(path, request_params)
            rows.extend(payload.get("bars", []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return rows

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _map_timeframe(bar_size: str) -> str:
        normalized = bar_size.strip().lower()
        if normalized in {"1 min", "1min"}:
            return "1Min"
        if normalized in {"5 mins", "5 min", "5mins", "5min"}:
            return "5Min"
        if normalized in {"15 mins", "15 min", "15mins", "15min"}:
            return "15Min"
        if normalized in {"1 hour", "1h", "60 min", "60 mins"}:
            return "1Hour"
        return "1Min"

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value).astimezone(timezone.utc)
