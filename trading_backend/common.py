from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


US_EASTERN = ZoneInfo("America/New_York")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def log(message: str) -> None:
    print(f"[{utc_now().strftime('%H:%M:%S')}] trading-backend > {message}")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_firestore_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "quota exceeded" in text or "resource exhausted" in text

