from __future__ import annotations

from decimal import Decimal

from stable_coin_trader.config import BotConfig
from stable_coin_trader.models import Opportunity, ProposedTrade, ResearchSignal, RiskDecision


class RiskEngine:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def evaluate(
        self,
        trade: ProposedTrade,
        opportunity: Opportunity,
        signals: list[ResearchSignal],
        current_position_usd: Decimal = Decimal("0"),
    ) -> RiskDecision:
        scoped_signals = self._signals_for_opportunity(opportunity, signals)
        human_review_signals = [
            signal for signal in scoped_signals if signal.human_review_required
        ]
        tightening_signals = [
            signal for signal in scoped_signals if signal.direction == "risk_increase"
        ]
        active_signals_by_id = {
            signal.id: signal for signal in [*human_review_signals, *tightening_signals]
        }
        active_signals = sorted(active_signals_by_id.values(), key=lambda signal: signal.id)
        active_signal_ids = [signal.id for signal in active_signals]

        if not self._trade_matches_opportunity(trade, opportunity):
            return RiskDecision.reject(
                trade=trade,
                reason="trade does not match opportunity",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        if not self._opportunity_is_configured(opportunity):
            return RiskDecision.reject(
                trade=trade,
                reason="trade outside configured universe",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        notional = trade.size * trade.limit_price
        if current_position_usd + notional > self.config.max_position_usd:
            return RiskDecision.reject(
                trade=trade,
                reason="order exceeds max position size",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        if notional > self.config.max_order_usd:
            return RiskDecision.reject(
                trade=trade,
                reason="order exceeds max order size",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        if human_review_signals:
            return RiskDecision.reject(
                trade=trade,
                reason="human review required by research signal",
                min_edge_bps=self.config.min_edge_bps,
                requires_human_approval=True,
                active_signal_ids=active_signal_ids,
            )

        min_edge = self._min_edge_with_signal_buffer(tightening_signals)
        if opportunity.net_edge_bps < min_edge:
            return RiskDecision.reject(
                trade=trade,
                reason="net edge below minimum",
                min_edge_bps=min_edge,
                active_signal_ids=active_signal_ids,
            )

        return RiskDecision.approve(
            trade=trade,
            reason="approved",
            min_edge_bps=min_edge,
            active_signal_ids=active_signal_ids,
        )

    def _signals_for_opportunity(
        self,
        opportunity: Opportunity,
        signals: list[ResearchSignal],
    ) -> list[ResearchSignal]:
        base_asset = opportunity.symbol.split("/", maxsplit=1)[0]
        venues = {opportunity.buy_venue, opportunity.sell_venue}
        return sorted(
            (
                signal
                for signal in signals
                if (
                    base_asset in signal.affected_assets
                    or venues.intersection(signal.affected_venues)
                )
            ),
            key=lambda signal: signal.id,
        )

    def _min_edge_with_signal_buffer(self, signals: list[ResearchSignal]) -> Decimal:
        buffer = sum((signal.risk_score for signal in signals), Decimal("0"))
        return self.config.min_edge_bps + buffer

    def _trade_matches_opportunity(
        self,
        trade: ProposedTrade,
        opportunity: Opportunity,
    ) -> bool:
        if trade.opportunity_id != opportunity.id:
            return False
        if trade.symbol != opportunity.symbol:
            return False
        if trade.size != opportunity.size:
            return False

        if trade.side == "buy":
            return (
                trade.venue == opportunity.buy_venue
                and trade.limit_price == opportunity.buy_price
            )

        if trade.side == "sell":
            return (
                trade.venue == opportunity.sell_venue
                and trade.limit_price == opportunity.sell_price
            )

        return False

    def _opportunity_is_configured(self, opportunity: Opportunity) -> bool:
        return (
            opportunity.symbol in self.config.symbols
            and opportunity.buy_venue in self.config.venues
            and opportunity.sell_venue in self.config.venues
        )
