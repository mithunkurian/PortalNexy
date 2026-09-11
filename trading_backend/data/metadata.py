from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from trading_backend.models import RuntimeConfig, WatchlistItem


class MetadataRepository:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        default_path = Path(__file__).resolve().parent.parent / "config" / f"watchlist.{config.runtime_id}.json"
        self.path = Path(config.metadata_path) if config.metadata_path else default_path
        self.watchlist = self._load_watchlist()

    def _load_watchlist(self) -> list[WatchlistItem]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        items: list[WatchlistItem] = []
        for row in payload:
            earnings_dates = []
            for value in row.get("earnings_dates", []):
                try:
                    earnings_dates.append(date.fromisoformat(value))
                except ValueError:
                    continue
            items.append(
                WatchlistItem(
                    symbol=row["symbol"].upper(),
                    name=row.get("name", row["symbol"].upper()),
                    sector=row.get("sector", "Unknown"),
                    asset_type=row.get("asset_type", "stock"),
                    large_cap=bool(row.get("large_cap", False)),
                    liquid_etf=bool(row.get("liquid_etf", False)),
                    min_avg_volume=int(row.get("min_avg_volume", 0)),
                    max_spread_bps=float(row.get("max_spread_bps", 25)),
                    earnings_dates=earnings_dates,
                    enabled=bool(row.get("enabled", True)),
                )
            )
        return [item for item in items if item.enabled]

    def active_items(self) -> list[WatchlistItem]:
        return list(self.watchlist)

    def to_snapshot(self) -> list[dict]:
        snapshot: list[dict] = []
        for item in self.watchlist:
            row = asdict(item)
            row["earnings_dates"] = [d.isoformat() for d in item.earnings_dates]
            snapshot.append(row)
        return snapshot

