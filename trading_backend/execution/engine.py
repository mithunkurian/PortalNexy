from __future__ import annotations

from trading_backend.models import PositionPlan, Proposal


class ExecutionEngine:
    def __init__(self, broker) -> None:
        self.broker = broker

    def submit_entry(self, proposal: Proposal) -> tuple[dict, PositionPlan]:
        if not proposal.symbol or not proposal.entry_trigger_price or not proposal.stop_loss:
            raise RuntimeError("Proposal is missing entry or stop details.")
        entry = self.broker.submit_stop_entry(proposal.symbol, proposal.quantity, proposal.entry_trigger_price)
        plan = PositionPlan(
            symbol=proposal.symbol,
            quantity=proposal.quantity,
            entry_price=proposal.entry_trigger_price,
            stop_price=proposal.stop_loss,
            target_1r=proposal.entry_trigger_price + (proposal.risk_per_share or 0),
            target_2r=proposal.entry_trigger_price + (2 * (proposal.risk_per_share or 0)),
            ema10=0.0,
            sector=proposal.sector or "Unknown",
            risk_per_share=proposal.risk_per_share or 0.0,
            entry_order_id=entry.get("order_id"),
        )
        return entry, plan

    def place_initial_stop(self, plan: PositionPlan) -> dict:
        stop = self.broker.submit_protective_stop(plan.symbol, plan.quantity, plan.stop_price)
        plan.stop_order_id = stop.get("order_id")
        return stop

    def flatten_position(self, symbol: str, quantity: int) -> dict:
        return self.broker.submit_market_exit(symbol, "SELL", quantity)
