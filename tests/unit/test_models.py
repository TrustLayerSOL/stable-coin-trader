from collections.abc import Callable
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


def test_parse_dt_only_treats_trailing_z_as_utc() -> None:
    with pytest.raises(ValueError):
        parse_dt("2026-05-13ZT12:00:00Z")


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
    assert opportunity.net_edge_bps.quantize(Decimal("0.0001")) == Decimal("0.5003")


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("size", Decimal("0")),
        ("size", Decimal("-1")),
        ("buy_price", Decimal("0")),
        ("buy_price", Decimal("-0.0001")),
        ("sell_price", Decimal("0")),
        ("sell_price", Decimal("-0.0001")),
        ("estimated_fees", Decimal("-0.01")),
        ("estimated_slippage", Decimal("-0.01")),
    ],
)
def test_opportunity_rejects_invalid_monetary_values(
    field_name: str,
    invalid_value: Decimal,
) -> None:
    values = {
        "buy_venue": "kraken",
        "sell_venue": "coinbase",
        "symbol": "USDC/USD",
        "size": Decimal("1000"),
        "buy_price": Decimal("0.9995"),
        "sell_price": Decimal("1.0000"),
        "estimated_fees": Decimal("0.40"),
        "estimated_slippage": Decimal("0.05"),
        "observed_at": "2026-05-13T12:00:00Z",
    }
    values[field_name] = invalid_value

    with pytest.raises(ValidationError):
        Opportunity(**values)


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


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("size", Decimal("0")),
        ("size", Decimal("-1")),
        ("limit_price", Decimal("0")),
        ("limit_price", Decimal("-0.0001")),
    ],
)
def test_proposed_trade_rejects_invalid_size_and_limit_price(
    field_name: str,
    invalid_value: Decimal,
) -> None:
    values = {
        "opportunity_id": "opp-1",
        "side": "buy",
        "venue": "kraken",
        "symbol": "USDC/USD",
        "size": Decimal("1000"),
        "limit_price": Decimal("0.9995"),
    }
    values[field_name] = invalid_value

    with pytest.raises(ValidationError):
        ProposedTrade(**values)


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
    assert signal.is_expired(datetime(2026, 5, 13, 13, 0, 0, tzinfo=timezone.utc)) is False
    assert signal.is_expired(datetime(2026, 5, 13, 13, 0, 1, tzinfo=timezone.utc)) is True


def test_research_signal_risk_score_multiplies_severity_confidence_source_quality() -> None:
    signal = make_research_signal(severity=4, confidence=0.5, source_quality=0.75)

    assert signal.risk_score == Decimal("1.5")


def test_research_signal_risk_score_avoids_float_noise() -> None:
    signal = make_research_signal(severity=3, confidence=0.1, source_quality=0.1)

    assert signal.risk_score == Decimal("0.03")


def test_parse_dt_rejects_invalid_type_with_clear_error() -> None:
    with pytest.raises(ValueError, match="datetime|string|str|ISO"):
        parse_dt(123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: MarketSnapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid=Decimal("0.9998"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at=123,
        ),
        lambda: Opportunity(
            buy_venue="kraken",
            sell_venue="coinbase",
            symbol="USDC/USD",
            size=Decimal("1000"),
            buy_price=Decimal("0.9995"),
            sell_price=Decimal("1.0000"),
            estimated_fees=Decimal("0.40"),
            estimated_slippage=Decimal("0.05"),
            observed_at=123,
        ),
        lambda: make_research_signal(observed_at=123),
        lambda: make_research_signal(published_at=123),
    ],
)
def test_datetime_models_reject_invalid_datetime_types(
    model_factory: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError):
        model_factory()


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: MarketSnapshot(
            venue="",
            symbol="USDC/USD",
            bid=Decimal("0.9998"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: MarketSnapshot(
            venue="coinbase",
            symbol="",
            bid=Decimal("0.9998"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: Opportunity(
            id="",
            buy_venue="kraken",
            sell_venue="coinbase",
            symbol="USDC/USD",
            size=Decimal("1000"),
            buy_price=Decimal("0.9995"),
            sell_price=Decimal("1.0000"),
            estimated_fees=Decimal("0.40"),
            estimated_slippage=Decimal("0.05"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: Opportunity(
            buy_venue="",
            sell_venue="coinbase",
            symbol="USDC/USD",
            size=Decimal("1000"),
            buy_price=Decimal("0.9995"),
            sell_price=Decimal("1.0000"),
            estimated_fees=Decimal("0.40"),
            estimated_slippage=Decimal("0.05"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: Opportunity(
            buy_venue="kraken",
            sell_venue="",
            symbol="USDC/USD",
            size=Decimal("1000"),
            buy_price=Decimal("0.9995"),
            sell_price=Decimal("1.0000"),
            estimated_fees=Decimal("0.40"),
            estimated_slippage=Decimal("0.05"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: ProposedTrade(
            opportunity_id="",
            side="buy",
            venue="kraken",
            symbol="USDC/USD",
            size=Decimal("1000"),
            limit_price=Decimal("0.9995"),
        ),
        lambda: ProposedTrade(
            opportunity_id="opp-1",
            side="buy",
            venue="",
            symbol="USDC/USD",
            size=Decimal("1000"),
            limit_price=Decimal("0.9995"),
        ),
        lambda: make_research_signal(id=""),
        lambda: make_research_signal(source=""),
        lambda: make_research_signal(source_url=""),
        lambda: make_research_signal(summary=""),
        lambda: make_research_signal(affected_assets=[""]),
        lambda: make_research_signal(affected_venues=[""]),
        lambda: RiskDecision.reject(trade=make_trade(), reason=""),
        lambda: RiskDecision.approve(
            trade=make_trade(),
            reason="edge clears threshold",
            min_edge_bps=Decimal("2.5"),
            active_signal_ids=[""],
        ),
    ],
)
def test_models_reject_empty_identity_and_reason_strings(
    model_factory: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError):
        model_factory()


@pytest.mark.parametrize(
    "model_factory",
    [
        lambda: MarketSnapshot(
            venue="   ",
            symbol="USDC/USD",
            bid=Decimal("0.9998"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        lambda: ProposedTrade(
            opportunity_id="opp-1",
            side="buy",
            venue="kraken",
            symbol="   ",
            size=Decimal("1000"),
            limit_price=Decimal("0.9995"),
        ),
        lambda: make_research_signal(source_url="   "),
        lambda: RiskDecision.reject(trade=make_trade(), reason="   "),
    ],
)
def test_models_reject_whitespace_only_identity_and_reason_strings(
    model_factory: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError):
        model_factory()


def test_risk_decision_rejects_negative_min_edge_bps() -> None:
    with pytest.raises(ValidationError):
        RiskDecision.reject(
            trade=make_trade(),
            reason="edge below threshold",
            min_edge_bps=Decimal("-0.01"),
        )


def test_research_signal_rejects_published_after_observed() -> None:
    with pytest.raises(ValidationError):
        make_research_signal(
            observed_at="2026-05-13T12:00:00Z",
            published_at="2026-05-13T12:00:01Z",
        )


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
