from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from trading_backend.common import utc_now
from trading_backend.models import Proposal, RiskDecision, StrategyCandidate


class ProposalManager:
    def empty(self, mode: str, reason: str = "No active proposal.") -> Proposal:
        now = utc_now()
        return Proposal(
            proposal_id=None,
            symbol=None,
            side=None,
            quantity=0,
            order_type=None,
            entry_trigger_price=None,
            stop_loss=None,
            take_profit=None,
            risk_reward=None,
            risk_per_share=None,
            score=None,
            confidence_score=None,
            sector=None,
            strategy_tag="v1.2_pullback_long",
            rationale=reason,
            proposal_status="None",
            approval_required=mode != "Agent",
            mode=mode,
            created_at=now,
            last_validated_at=now,
            expires_at=None,
        )

    def from_candidate(self, candidate: StrategyCandidate, decision: RiskDecision, mode: str, status: str = "Active") -> Proposal:
        now = utc_now()
        rr = ((candidate.entry_trigger_price + (2 * candidate.risk_per_share)) - candidate.entry_trigger_price) / candidate.risk_per_share if candidate.risk_per_share else None
        return Proposal(
            proposal_id=uuid4().hex[:12],
            symbol=candidate.symbol,
            side="BUY",
            quantity=decision.quantity,
            order_type="BUY STOP",
            entry_trigger_price=round(candidate.entry_trigger_price, 4),
            stop_loss=round(candidate.stop_price, 4),
            take_profit=round(candidate.entry_trigger_price + (2 * candidate.risk_per_share), 4),
            risk_reward=round(rr, 4) if rr is not None else None,
            risk_per_share=round(candidate.risk_per_share, 4),
            score=round(candidate.score, 4),
            confidence_score=round(candidate.confidence_score, 4),
            sector=candidate.sector,
            strategy_tag="v1.2_pullback_long",
            rationale=candidate.rationale,
            proposal_status=status,
            approval_required=mode != "Agent",
            mode=mode,
            created_at=now,
            last_validated_at=now,
            expires_at=now + timedelta(seconds=60),
            valid_for_date=candidate.valid_for_date,
            validation_snapshot=decision.checks,
        )

    def invalidate(self, proposal: Proposal, reason: str, status: str = "Invalidated") -> Proposal:
        proposal.proposal_status = status
        proposal.invalid_reason = reason
        proposal.last_validated_at = utc_now()
        proposal.expires_at = utc_now()
        return proposal
