from datetime import datetime, timezone
from decimal import Decimal

import pytest

from stable_coin_trader.models import MarketSnapshot
from stable_coin_trader.opportunities import find_spread_opportunities


def make_snapshot(
    *,
    venue: str,
    symbol: str = "USDC/USD",
    bid: str = "1.0000",
    ask: str = "1.0002",
    bid_size: str = "50000",
    ask_size: str = "50000",
    observed_at: str = "2026-05-13T12:00:00Z",
) -> MarketSnapshot:
    return MarketSnapshot(
        venue=venue,
        symbol=symbol,
        bid=Decimal(bid),
        ask=Decimal(ask),
        bid_size=Decimal(bid_size),
        ask_size=Decimal(ask_size),
        observed_at=observed_at,
    )


def test_find_spread_opportunities_returns_profitable_cross_venue_trade() -> None:
    snapshots = [
        make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.buy_venue == "kraken"
    assert opportunity.sell_venue == "coinbase"
    assert opportunity.symbol == "USDC/USD"
    assert opportunity.size == Decimal("1000")
    assert opportunity.buy_price == Decimal("0.9996")
    assert opportunity.sell_price == Decimal("1.0000")
    assert opportunity.net_profit > 0


def test_find_spread_opportunities_uses_stable_observation_scoped_ids() -> None:
    snapshots = [
        make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
    ]
    later_snapshots = [
        make_snapshot(
            venue="coinbase",
            bid="1.0000",
            ask="1.0002",
            observed_at="2026-05-13T12:00:01Z",
        ),
        make_snapshot(
            venue="kraken",
            bid="0.9994",
            ask="0.9996",
            observed_at="2026-05-13T12:00:01Z",
        ),
    ]
    scaled_snapshots = [
        make_snapshot(venue="coinbase", bid="1.00000", ask="1.00020"),
        make_snapshot(venue="kraken", bid="0.99940", ask="0.99960"),
    ]

    first = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )
    replay = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )
    later = find_spread_opportunities(
        snapshots=later_snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )
    scaled = find_spread_opportunities(
        snapshots=scaled_snapshots,
        size=Decimal("1000.0"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert first[0].id == replay[0].id
    assert scaled[0].id == first[0].id
    assert later[0].id != first[0].id


def test_find_spread_opportunities_ignores_same_venue() -> None:
    snapshots = [
        make_snapshot(venue="coinbase"),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert opportunities == []


def test_find_spread_opportunities_groups_prices_by_symbol() -> None:
    snapshots = [
        make_snapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid="1.0100",
            ask="1.0102",
        ),
        make_snapshot(
            venue="kraken",
            symbol="USDT/USD",
            bid="0.9900",
            ask="0.9902",
        ),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    assert opportunities == []


def test_find_spread_opportunities_caps_size_by_available_depth() -> None:
    snapshots = [
        make_snapshot(
            venue="coinbase",
            bid="1.0000",
            ask="1.0002",
            bid_size="300",
            ask_size="50000",
        ),
        make_snapshot(
            venue="kraken",
            bid="0.9994",
            ask="0.9996",
            bid_size="50000",
            ask_size="200",
        ),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    assert len(opportunities) == 1
    assert opportunities[0].size == Decimal("200")
    assert opportunities[0].gross_profit == Decimal("0.0800")


def test_find_spread_opportunities_caps_size_by_sell_side_depth() -> None:
    snapshots = [
        make_snapshot(
            venue="coinbase",
            bid="1.0000",
            ask="1.0002",
            bid_size="150",
            ask_size="50000",
        ),
        make_snapshot(
            venue="kraken",
            bid="0.9994",
            ask="0.9996",
            bid_size="50000",
            ask_size="500",
        ),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    assert len(opportunities) == 1
    assert opportunities[0].size == Decimal("150")


def test_find_spread_opportunities_ignores_unprofitable_spreads() -> None:
    snapshots = [
        make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        make_snapshot(venue="kraken", bid="0.9998", ask="1.0001"),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    assert opportunities == []


def test_find_spread_opportunities_subtracts_fee_and_slippage_costs() -> None:
    snapshots = [
        make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.estimated_fees == Decimal("0.19996")
    assert opportunity.estimated_slippage == Decimal("0.09998")
    assert opportunity.gross_profit == Decimal("0.4000")
    assert opportunity.net_profit == Decimal("0.10006")


@pytest.mark.parametrize(
    ("size", "fee_bps", "slippage_bps"),
    [
        (Decimal("0"), Decimal("0"), Decimal("0")),
        (Decimal("-1"), Decimal("0"), Decimal("0")),
        (Decimal("NaN"), Decimal("0"), Decimal("0")),
        (Decimal("Infinity"), Decimal("0"), Decimal("0")),
        (Decimal("-Infinity"), Decimal("0"), Decimal("0")),
        (Decimal("1000"), Decimal("-0.01"), Decimal("0")),
        (Decimal("1000"), Decimal("NaN"), Decimal("0")),
        (Decimal("1000"), Decimal("Infinity"), Decimal("0")),
        (Decimal("1000"), Decimal("-Infinity"), Decimal("0")),
        (Decimal("1000"), Decimal("0"), Decimal("-0.01")),
        (Decimal("1000"), Decimal("0"), Decimal("NaN")),
        (Decimal("1000"), Decimal("0"), Decimal("Infinity")),
        (Decimal("1000"), Decimal("0"), Decimal("-Infinity")),
    ],
)
def test_find_spread_opportunities_rejects_invalid_numeric_inputs(
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> None:
    with pytest.raises(ValueError):
        find_spread_opportunities(
            snapshots=[],
            size=size,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )


def test_find_spread_opportunities_sorts_by_net_profit_deterministically() -> None:
    snapshots = [
        make_snapshot(
            venue="coinbase",
            bid="1.0012",
            ask="1.0014",
            observed_at="2026-05-13T12:01:00Z",
        ),
        make_snapshot(
            venue="bitstamp",
            bid="1.0010",
            ask="1.0012",
            observed_at="2026-05-13T12:01:30Z",
        ),
        make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
        make_snapshot(
            venue="gemini",
            bid="0.9995",
            ask="0.9996",
            observed_at="2026-05-13T12:02:00Z",
        ),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    ordered_pairs = [
        (opportunity.buy_venue, opportunity.sell_venue)
        for opportunity in opportunities
    ]

    assert ordered_pairs == [
        ("gemini", "coinbase"),
        ("kraken", "coinbase"),
        ("gemini", "bitstamp"),
        ("kraken", "bitstamp"),
    ]
    assert [opportunity.net_profit for opportunity in opportunities] == [
        Decimal("1.6000"),
        Decimal("1.6000"),
        Decimal("1.4000"),
        Decimal("1.4000"),
    ]
    assert opportunities[0].observed_at == datetime(
        2026, 5, 13, 12, 2, tzinfo=timezone.utc
    )
