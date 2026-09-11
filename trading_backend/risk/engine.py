from __future__ import annotations

from typing import Any

from trading_backend.common import safe_float
from trading_backend.models import RiskDecision, StrategyCandidate, WatchlistItem


class RiskEngine:
    def evaluate_entry(
        self,
        candidate: StrategyCandidate,
        account: dict[str, Any],
        positions: list[dict[str, Any]],
        state: dict[str, Any],
        fx_usdsek: float,
        item: WatchlistItem,
    ) -> RiskDecision:
        equity = safe_float(account.get("net_liquidation"))
        if equity <= 0:
            return RiskDecision(False, "Missing account equity.", {"equity": equity})

        risk_amount_usd = equity * 0.01
        quantity = int(risk_amount_usd / candidate.risk_per_share) if candidate.risk_per_share > 0 else 0
        notional_usd = quantity * candidate.entry_trigger_price
        notional_sek = notional_usd * fx_usdsek
        risk_amount_sek = risk_amount_usd * fx_usdsek
        checks = {
            "equity_usd": equity,
            "risk_amount_usd": risk_amount_usd,
            "risk_amount_sek": risk_amount_sek,
            "quantity": quantity,
            "notional_usd": notional_usd,
            "notional_sek": notional_sek,
            "open_positions": len([p for p in positions if safe_float(p.get("quantity")) != 0]),
            "sector_conflict": any((p.get("sector") or "") == item.sector for p in positions if safe_float(p.get("quantity")) != 0),
            "daily_lock": state.get("daily_lock", False),
            "weekly_lock": state.get("weekly_lock", False),
            "kill_switch_active": state.get("kill_switch_active", False),
            "new_trades_today": state.get("new_trades_today", 0),
            "portfolio_risk_pct": state.get("portfolio_risk_pct", 0.0),
        }
        if checks["daily_lock"] or checks["weekly_lock"] or checks["kill_switch_active"]:
            return RiskDecision(False, "Portfolio lock active.", checks)
        if checks["open_positions"] >= 2:
            return RiskDecision(False, "Max open positions reached.", checks)
        if checks["sector_conflict"]:
            return RiskDecision(False, "Sector already held.", checks)
        if checks["new_trades_today"] >= 1:
            return RiskDecision(False, "Max one new trade per day reached.", checks)
        if safe_float(checks["portfolio_risk_pct"]) >= 2.0:
            return RiskDecision(False, "Max portfolio risk reached.", checks)
        if quantity < 5:
            return RiskDecision(False, "Size below 5 shares.", checks)
        if notional_sek < 1000:
            return RiskDecision(False, "Position notional below 1,000 SEK.", checks)
        return RiskDecision(
            True,
            "Risk checks passed.",
            checks,
            quantity=quantity,
            notional_usd=notional_usd,
            risk_amount_usd=risk_amount_usd,
            risk_amount_sek=risk_amount_sek,
        )
