from __future__ import annotations

from decimal import Decimal

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import RiskDecision


class PaperExecutor:
    def __init__(self, ledger: Ledger, fee_bps: Decimal) -> None:
        if not isinstance(fee_bps, Decimal):
            raise TypeError("fee_bps must be a Decimal")
        if not fee_bps.is_finite() or fee_bps < 0:
            raise ValueError("fee_bps must be nonnegative and finite")

        self.ledger = ledger
        self.fee_bps = fee_bps

    def execute(self, decision: RiskDecision) -> int | None:
        risk_decision_id = self.ledger.record_risk_decision(decision)
        if not decision.approved:
            return None

        trade = decision.trade
        notional = trade.size * trade.limit_price
        fee = notional * self.fee_bps / Decimal("10000")
        return self.ledger.record_paper_fill(
            risk_decision_id=risk_decision_id,
            opportunity_id=trade.opportunity_id,
            venue=trade.venue,
            symbol=trade.symbol,
            side=trade.side,
            size=trade.size,
            price=trade.limit_price,
            fee=fee,
        )
