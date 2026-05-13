from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from stable_coin_trader.models import (
    MarketSnapshot,
    Opportunity,
    ProposedTrade,
    ResearchSignal,
    RiskDecision,
    parse_dt,
    utc_now,
)


def make_trade() -> ProposedTrade:
    return ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )


def make_research_signal(**overrides: object) -> ResearchSignal:
    values = {
        "id": "sig-1",
        "observed_at": "2026-05-13T12:00:00Z",
        "published_at": "2026-05-13T11:59:00Z",
        "source": "fixture",
        "source_url": "https://example.com/signal",
        "source_quality": 0.7,
        "affected_assets": ["USDC"],
        "affected_venues": ["coinbase"],
        "event_type": "venue_outage",
        "direction": "risk_increase",
        "severity": 3,
        "confidence": 0.8,
        "ttl_seconds": 3600,
        "summary": "Venue outage increases risk.",
    }
    values.update(overrides)
    return ResearchSignal(**values)


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    current = utc_now()

    assert current.tzinfo is not None
    assert current.utcoffset() == timedelta(0)
    assert current.tzinfo == timezone.utc


def test_parse_dt_handles_trailing_z_and_normalizes_to_utc() -> None:
    parsed = parse_dt("2026-05-13T12:00:00Z")
    shifted = parse_dt("2026-05-13T08:00:00-04:00")
    naive = parse_dt(datetime(2026, 5, 13, 12, 0, 0))

    expected = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    assert parsed == expected
    assert shifted == expected
    assert naive == expected


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


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("bid", Decimal("0")),
        ("bid", Decimal("-0.0001")),
        ("ask", Decimal("0")),
        ("ask", Decimal("-0.0001")),
        ("bid_size", Decimal("-1")),
        ("ask_size", Decimal("-1")),
    ],
)
def test_market_snapshot_rejects_non_positive_prices_and_negative_sizes(
    field_name: str,
    invalid_value: Decimal,
) -> None:
    values = {
        "venue": "coinbase",
        "symbol": "USDC/USD",
        "bid": Decimal("0.9998"),
        "ask": Decimal("1.0000"),
        "bid_size": Decimal("50000"),
        "ask_size": Decimal("75000"),
        "observed_at": "2026-05-13T12:00:00Z",
    }
    values[field_name] = invalid_value

    with pytest.raises(ValidationError):
        MarketSnapshot(**values)


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


def test_opportunity_default_id_is_uuid_string() -> None:
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

    assert str(UUID(opportunity.id)) == opportunity.id


def test_proposed_trade_rejects_invalid_side() -> None:
    with pytest.raises(ValidationError):
        ProposedTrade(
            opportunity_id="opp-1",
            side="hold",
            venue="kraken",
            symbol="USDC/USD",
            size=Decimal("1000"),
            limit_price=Decimal("0.9995"),
        )


def test_research_signal_requires_valid_direction() -> None:
    with pytest.raises(ValidationError):
        make_research_signal(direction="buy_now")


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("source_quality", 1.1),
        ("source_quality", -0.1),
        ("severity", 6),
        ("severity", -1),
        ("confidence", 1.1),
        ("confidence", -0.1),
    ],
)
def test_research_signal_rejects_invalid_score_ranges(
    field_name: str,
    invalid_value: float | int,
) -> None:
    with pytest.raises(ValidationError):
        make_research_signal(**{field_name: invalid_value})


def test_research_signal_is_expired_uses_ttl_boundary() -> None:
    signal = make_research_signal(ttl_seconds=3600)

    assert signal.is_expired(datetime(2026, 5, 13, 12, 59, 59, tzinfo=timezone.utc)) is False
    assert signal.is_expired(datetime(2026, 5, 13, 13, 0, 1, tzinfo=timezone.utc)) is True


def test_research_signal_risk_score_multiplies_severity_confidence_source_quality() -> None:
    signal = make_research_signal(severity=4, confidence=0.5, source_quality=0.75)

    assert signal.risk_score == Decimal("1.5")


def test_risk_decision_explains_rejection() -> None:
    trade = make_trade()
    decision = RiskDecision.reject(trade=trade, reason="net edge below minimum")

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.requires_human_approval is False


def test_risk_decision_approve_sets_reason_min_edge_and_active_signal_ids() -> None:
    trade = make_trade()

    decision = RiskDecision.approve(
        trade=trade,
        reason="edge clears research-adjusted threshold",
        min_edge_bps=Decimal("2.5"),
        active_signal_ids=["sig-1", "sig-2"],
    )

    assert decision.trade == trade
    assert decision.approved is True
    assert decision.reason == "edge clears research-adjusted threshold"
    assert decision.min_edge_bps == Decimal("2.5")
    assert decision.active_signal_ids == ["sig-1", "sig-2"]
