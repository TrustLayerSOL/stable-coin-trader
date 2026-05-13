import json
from decimal import Decimal

import pytest

from stable_coin_trader.models import MarketSnapshot
from stable_coin_trader.spread_observations import (
    append_spread_observations,
    build_spread_observations,
    load_spread_observations,
    summarize_spread_observations,
)


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


def test_build_spread_observations_records_profitable_and_unprofitable_routes() -> None:
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(
                venue="kraken",
                bid="0.9994",
                ask="0.9996",
                bid_size="2000",
                ask_size="600",
            ),
            make_snapshot(
                venue="coinbase",
                bid="1.0000",
                ask="1.0002",
                bid_size="500",
                ask_size="1500",
                observed_at="2026-05-13T12:00:01Z",
            ),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    assert len(observations) == 2

    best = observations[0]
    assert best.buy_venue == "kraken"
    assert best.sell_venue == "coinbase"
    assert best.symbol == "USDC/USD"
    assert best.requested_size == Decimal("1000")
    assert best.size == Decimal("500")
    assert best.buy_price == Decimal("0.9996")
    assert best.sell_price == Decimal("1.0000")
    assert best.buy_notional == Decimal("499.8000")
    assert best.sell_notional == Decimal("500.0000")
    assert best.estimated_fees == Decimal("0.09998")
    assert best.estimated_slippage == Decimal("0.049990")
    assert best.gross_profit == Decimal("0.2000")
    assert best.net_profit == Decimal("0.050030")
    assert best.snapshot_lag_seconds == Decimal("1")
    assert best.buy_observed_at.isoformat() == "2026-05-13T12:00:00+00:00"
    assert best.sell_observed_at.isoformat() == "2026-05-13T12:00:01+00:00"
    assert best.observed_at.isoformat() == "2026-05-13T12:00:01+00:00"
    assert best.is_profitable is True

    worst = observations[1]
    assert worst.buy_venue == "coinbase"
    assert worst.sell_venue == "kraken"
    assert worst.size == Decimal("1000")
    assert worst.net_profit < 0
    assert worst.is_profitable is False


def test_build_spread_observations_skips_stale_cross_venue_pairs() -> None:
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(venue="kraken", observed_at="2026-05-13T12:00:00Z"),
            make_snapshot(venue="coinbase", observed_at="2026-05-13T12:00:10Z"),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    assert observations == []


def test_build_spread_observations_allows_pairs_at_exact_lag_limit() -> None:
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(venue="kraken", observed_at="2026-05-13T12:00:00Z"),
            make_snapshot(venue="coinbase", observed_at="2026-05-13T12:00:05Z"),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    assert len(observations) == 2
    assert {observation.snapshot_lag_seconds for observation in observations} == {
        Decimal("5")
    }


def test_build_spread_observations_skips_same_venue_symbols_and_zero_depth() -> None:
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(venue="kraken", symbol="USDC/USD"),
            make_snapshot(venue="kraken", symbol="USDC/USD"),
            make_snapshot(venue="coinbase", symbol="PYUSD/USD"),
            make_snapshot(
                venue="gemini",
                symbol="PYUSD/USD",
                bid_size="0",
                ask_size="0",
            ),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    assert observations == []


def test_spread_observation_summary_reports_best_route_and_averages() -> None:
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
            make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    summary = summarize_spread_observations(observations)

    assert summary.observation_count == 2
    assert summary.profitable_count == 1
    assert summary.best_route == "kraken->coinbase USDC/USD"
    assert summary.best_net_profit == Decimal("0.4000")
    assert summary.average_net_profit == Decimal("-0.2000")
    assert summary.first_observed_at.isoformat() == "2026-05-13T12:00:00+00:00"
    assert summary.last_observed_at.isoformat() == "2026-05-13T12:00:00+00:00"


def test_spread_observation_summary_handles_empty_history() -> None:
    summary = summarize_spread_observations([])

    assert summary.observation_count == 0
    assert summary.profitable_count == 0
    assert summary.best_route is None
    assert summary.best_net_profit is None
    assert summary.average_net_profit is None


def test_append_and_load_spread_observations_round_trip_jsonl(tmp_path) -> None:
    path = tmp_path / "observations.jsonl"
    observations = build_spread_observations(
        snapshots=[
            make_snapshot(venue="kraken", bid="0.9994", ask="0.9996"),
            make_snapshot(venue="coinbase", bid="1.0000", ask="1.0002"),
        ],
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
    )

    append_spread_observations(path, observations)
    append_spread_observations(path, observations[:1])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    first_line = json.loads(lines[0])
    assert first_line["buy_venue"] == "kraken"
    assert first_line["profitable"] is True
    assert first_line["observed_at"] == "2026-05-13T12:00:00Z"

    loaded = load_spread_observations(path)
    assert [item.id for item in loaded] == [
        observations[0].id,
        observations[1].id,
        observations[0].id,
    ]
    assert loaded[0].net_profit == Decimal("0.4000")


def test_load_spread_observations_rejects_invalid_jsonl(tmp_path) -> None:
    path = tmp_path / "observations.jsonl"
    path.write_text("{bad json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_spread_observations(path)


def test_load_spread_observations_reports_line_for_malformed_object(tmp_path) -> None:
    path = tmp_path / "observations.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_spread_observations(path)


@pytest.mark.parametrize(
    ("size", "fee_bps", "slippage_bps", "max_lag"),
    [
        (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("5")),
        (Decimal("-1"), Decimal("0"), Decimal("0"), Decimal("5")),
        (Decimal("NaN"), Decimal("0"), Decimal("0"), Decimal("5")),
        (Decimal("1000"), Decimal("-0.01"), Decimal("0"), Decimal("5")),
        (Decimal("1000"), Decimal("NaN"), Decimal("0"), Decimal("5")),
        (Decimal("1000"), Decimal("0"), Decimal("-0.01"), Decimal("5")),
        (Decimal("1000"), Decimal("0"), Decimal("NaN"), Decimal("5")),
        (Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("-1")),
        (Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("NaN")),
    ],
)
def test_build_spread_observations_rejects_invalid_numeric_inputs(
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    max_lag: Decimal,
) -> None:
    with pytest.raises(ValueError):
        build_spread_observations(
            snapshots=[],
            size=size,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            max_snapshot_lag_seconds=max_lag,
        )
