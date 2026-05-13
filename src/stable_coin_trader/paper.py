from __future__ import annotations

from datetime import datetime
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

    def execute(
        self,
        decision: RiskDecision,
        created_at: datetime | None = None,
    ) -> int | None:
        if not decision.approved:
            self.ledger.record_risk_decision(decision, created_at=created_at)
            return None

        fill_ids = self.execute_many([decision], created_at=created_at)
        return fill_ids[0] if fill_ids else None

    def execute_many(
        self,
        decisions: list[RiskDecision],
        created_at: datetime | None = None,
    ) -> list[int]:
        if not decisions:
            return []

        if any(not decision.approved for decision in decisions):
            raise ValueError("execute_many requires approved decisions")

        fees = [self._fee_for(decision) for decision in decisions]
        return self.ledger.record_paper_fills_for_decisions(
            decisions=decisions,
            fees=fees,
            created_at=created_at,
        )

    def _fee_for(self, decision: RiskDecision) -> Decimal:
        trade = decision.trade
        notional = trade.size * trade.limit_price
        return notional * self.fee_bps / Decimal("10000")
