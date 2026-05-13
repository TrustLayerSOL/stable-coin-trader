from decimal import Decimal

import pytest
from pydantic import ValidationError

from stable_coin_trader.models import (
    MarketSnapshot,
    Opportunity,
    ProposedTrade,
    ResearchSignal,
    RiskDecision,
)


def test_market_snapshot_calculates_mid_price() -> None:
    snapshot = MarketSnapshot(
        venue="coinbase",
        symbol="USDC/USD",
        bid=Decimal("0.9998"),
        ask=Decimal("1.0000"),
        bid_size=Decimal("50000"),
        ask_size=Decimal("75000"),
        observed_at="2026-05-13T12:00:00Z",
    )

    assert snapshot.mid_price == Decimal("0.9999")


def test_market_snapshot_rejects_crossed_book() -> None:
    with pytest.raises(ValidationError):
        MarketSnapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid=Decimal("1.0001"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at="2026-05-13T12:00:00Z",
        )


def test_opportunity_net_edge_bps() -> None:
    opportunity = Opportunity(
        buy_venue="kraken",
        sell_venue="coinbase",
        symbol="USDC/USD",
        size=Decimal("1000"),
        buy_price=Decimal("0.9995"),
        sell_price=Decimal("1.0000"),
        estimated_fees=Decimal("0.40"),
        estimated_slippage=Decimal("0.05"),
        observed_at="2026-05-13T12:00:00Z",
    )

    assert opportunity.gross_profit == Decimal("0.5000")
    assert opportunity.net_profit == Decimal("0.0500")
    assert opportunity.notional == Decimal("999.5000")
    expected_edge = (opportunity.net_profit / opportunity.notional) * Decimal("10000")
    assert opportunity.net_edge_bps.quantize(Decimal("0.0001")) == expected_edge.quantize(
        Decimal("0.0001")
    )


def test_opportunity_net_edge_bps_returns_zero_for_non_positive_notional() -> None:
    opportunity = Opportunity(
        buy_venue="kraken",
        sell_venue="coinbase",
        symbol="USDC/USD",
        size=Decimal("1000"),
        buy_price=Decimal("0"),
        sell_price=Decimal("1.0000"),
        estimated_fees=Decimal("0.40"),
        estimated_slippage=Decimal("0.05"),
        observed_at="2026-05-13T12:00:00Z",
    )

    assert opportunity.notional == Decimal("0")
    assert opportunity.net_edge_bps == Decimal("0")


def test_research_signal_requires_valid_direction() -> None:
    with pytest.raises(ValidationError):
        ResearchSignal(
            id="sig-1",
            observed_at="2026-05-13T12:00:00Z",
            published_at="2026-05-13T11:59:00Z",
            source="fixture",
            source_url="https://example.com/signal",
            source_quality=0.7,
            affected_assets=["USDC"],
            affected_venues=["coinbase"],
            event_type="venue_outage",
            direction="buy_now",
            severity=3,
            confidence=0.8,
            ttl_seconds=3600,
            summary="Invalid direction should fail.",
        )


def test_risk_decision_explains_rejection() -> None:
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    decision = RiskDecision.reject(trade=trade, reason="net edge below minimum")

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.requires_human_approval is False
