from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from stable_coin_trader.coinbase import CoinbaseProductMapping
from stable_coin_trader.kraken import KrakenPairMapping
from stable_coin_trader.models import MarketSnapshot
from stable_coin_trader.spread_observations import load_spread_observations
from stable_coin_trader.spread_sampling import sample_spreads


class FakeClient:
    def __init__(self, venue: str, base_bid: Decimal, base_ask: Decimal) -> None:
        self.venue = venue
        self.base_bid = base_bid
        self.base_ask = base_ask
        self.calls = 0

    def fetch_order_book_snapshot(self, mapping):
        self.calls += 1
        observed_at = datetime(2026, 5, 13, 14, 0, tzinfo=timezone.utc) + timedelta(
            seconds=self.calls
        )
        return MarketSnapshot(
            venue=self.venue,
            symbol=mapping.symbol,
            bid=self.base_bid,
            ask=self.base_ask,
            bid_size=Decimal("2000"),
            ask_size=Decimal("2000"),
            observed_at=observed_at,
        )


class FailingOnceClient(FakeClient):
    def fetch_order_book_snapshot(self, mapping):
        if self.calls == 0:
            self.calls += 1
            raise ConnectionError("temporary public API failure")
        return super().fetch_order_book_snapshot(mapping)


class StaleClient(FakeClient):
    def __init__(
        self,
        venue: str,
        base_bid: Decimal,
        base_ask: Decimal,
        seconds: int,
    ) -> None:
        super().__init__(venue, base_bid, base_ask)
        self.seconds = seconds

    def fetch_order_book_snapshot(self, mapping):
        self.calls += 1
        return MarketSnapshot(
            venue=self.venue,
            symbol=mapping.symbol,
            bid=self.base_bid,
            ask=self.base_ask,
            bid_size=Decimal("2000"),
            ask_size=Decimal("2000"),
            observed_at=datetime(
                2026,
                5,
                13,
                14,
                0,
                self.seconds,
                tzinfo=timezone.utc,
            ),
        )


def test_sample_spreads_appends_observations_for_each_successful_sample(tmp_path):
    sleeps = []
    output = tmp_path / "spread_observations.jsonl"
    kraken_client = FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996"))
    coinbase_client = FakeClient("coinbase", Decimal("1.0000"), Decimal("1.0002"))

    result = sample_spreads(
        kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
        coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
        output_path=output,
        samples=2,
        interval_seconds=Decimal("0.25"),
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
        kraken_client=kraken_client,
        coinbase_client=coinbase_client,
        sleeper=sleeps.append,
    )

    assert result.samples_requested == 2
    assert result.samples_successful == 2
    assert result.samples_failed == 0
    assert result.observations_written == 4
    assert result.summary.observation_count == 4
    assert result.summary.profitable_count == 2
    assert result.summary.best_route == "kraken->coinbase USDC/USD"
    assert sleeps == [0.25]

    loaded = load_spread_observations(output)
    assert len(loaded) == 4
    assert [item.buy_venue for item in loaded[:2]] == ["kraken", "coinbase"]


def test_sample_spreads_counts_failure_and_continues_without_partial_write(tmp_path):
    sleeps = []
    output = tmp_path / "spread_observations.jsonl"
    kraken_client = FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996"))
    coinbase_client = FailingOnceClient(
        "coinbase",
        Decimal("1.0000"),
        Decimal("1.0002"),
    )

    result = sample_spreads(
        kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
        coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
        output_path=output,
        samples=2,
        interval_seconds=Decimal("0"),
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
        kraken_client=kraken_client,
        coinbase_client=coinbase_client,
        sleeper=sleeps.append,
    )

    assert result.samples_requested == 2
    assert result.samples_successful == 1
    assert result.samples_failed == 1
    assert result.observations_written == 2
    assert result.failures[0].sample_number == 1
    assert "temporary public API failure" in result.failures[0].reason
    assert sleeps == [0.0]
    assert len(load_spread_observations(output)) == 2


def test_sample_spreads_reports_per_sample_progress(tmp_path):
    progress = []
    output = tmp_path / "spread_observations.jsonl"
    kraken_client = FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996"))
    coinbase_client = FailingOnceClient(
        "coinbase",
        Decimal("1.0000"),
        Decimal("1.0002"),
    )

    def record_progress(
        sample_number,
        successful,
        observations_written,
        reason,
    ) -> None:
        progress.append((sample_number, successful, observations_written, reason))

    sample_spreads(
        kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
        coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
        output_path=output,
        samples=2,
        interval_seconds=Decimal("0"),
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
        kraken_client=kraken_client,
        coinbase_client=coinbase_client,
        sleeper=lambda seconds: None,
        on_sample_result=record_progress,
    )

    assert progress == [
        (1, False, 0, "temporary public API failure"),
        (2, True, 2, None),
    ]


def test_sample_spreads_treats_zero_observation_sample_as_success(tmp_path):
    output = tmp_path / "spread_observations.jsonl"

    result = sample_spreads(
        kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
        coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
        output_path=output,
        samples=1,
        interval_seconds=Decimal("0"),
        size=Decimal("1000"),
        fee_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        max_snapshot_lag_seconds=Decimal("5"),
        kraken_client=StaleClient(
            "kraken",
            Decimal("0.9994"),
            Decimal("0.9996"),
            seconds=0,
        ),
        coinbase_client=StaleClient(
            "coinbase",
            Decimal("1.0000"),
            Decimal("1.0002"),
            seconds=10,
        ),
        sleeper=lambda seconds: None,
    )

    assert result.samples_requested == 1
    assert result.samples_successful == 1
    assert result.samples_failed == 0
    assert result.observations_written == 0
    assert result.summary.observation_count == 0
    assert output.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize(
    ("samples", "interval_seconds", "size", "fee_bps", "slippage_bps", "max_lag"),
    [
        (0, Decimal("0"), Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("5")),
        (-1, Decimal("0"), Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("5")),
        (1, Decimal("-1"), Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("5")),
        (1, Decimal("NaN"), Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("5")),
        (
            1,
            Decimal("Infinity"),
            Decimal("1000"),
            Decimal("0"),
            Decimal("0"),
            Decimal("5"),
        ),
        (1, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("5")),
        (1, Decimal("0"), Decimal("1000"), Decimal("-1"), Decimal("0"), Decimal("5")),
        (
            1,
            Decimal("0"),
            Decimal("1000"),
            Decimal("Infinity"),
            Decimal("0"),
            Decimal("5"),
        ),
        (1, Decimal("0"), Decimal("1000"), Decimal("0"), Decimal("-1"), Decimal("5")),
        (
            1,
            Decimal("0"),
            Decimal("1000"),
            Decimal("0"),
            Decimal("Infinity"),
            Decimal("5"),
        ),
        (1, Decimal("0"), Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("-1")),
        (
            1,
            Decimal("0"),
            Decimal("1000"),
            Decimal("0"),
            Decimal("0"),
            Decimal("Infinity"),
        ),
    ],
)
def test_sample_spreads_rejects_invalid_inputs(
    tmp_path,
    samples,
    interval_seconds,
    size,
    fee_bps,
    slippage_bps,
    max_lag,
):
    with pytest.raises(ValueError):
        sample_spreads(
            kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
            coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
            output_path=tmp_path / "out.jsonl",
            samples=samples,
            interval_seconds=interval_seconds,
            size=size,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            max_snapshot_lag_seconds=max_lag,
            kraken_client=FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996")),
            coinbase_client=FakeClient(
                "coinbase",
                Decimal("1.0000"),
                Decimal("1.0002"),
            ),
            sleeper=lambda seconds: None,
        )


def test_sample_spreads_requires_at_least_one_mapping(tmp_path):
    with pytest.raises(ValueError, match="mapping"):
        sample_spreads(
            kraken_mappings=[],
            coinbase_mappings=[],
            output_path=tmp_path / "out.jsonl",
            samples=1,
            interval_seconds=Decimal("0"),
            size=Decimal("1000"),
            fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            max_snapshot_lag_seconds=Decimal("5"),
            kraken_client=FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996")),
            coinbase_client=FakeClient(
                "coinbase",
                Decimal("1.0000"),
                Decimal("1.0002"),
            ),
            sleeper=lambda seconds: None,
        )


def test_sample_spreads_rejects_interval_too_large_for_sleep(tmp_path):
    with pytest.raises(ValueError, match="interval_seconds is too large"):
        sample_spreads(
            kraken_mappings=[KrakenPairMapping("USDCUSD", "USDC/USD")],
            coinbase_mappings=[CoinbaseProductMapping("USDC-USD", "USDC/USD")],
            output_path=tmp_path / "out.jsonl",
            samples=2,
            interval_seconds=Decimal("1e10000"),
            size=Decimal("1000"),
            fee_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            max_snapshot_lag_seconds=Decimal("5"),
            kraken_client=FakeClient("kraken", Decimal("0.9994"), Decimal("0.9996")),
            coinbase_client=FakeClient(
                "coinbase",
                Decimal("1.0000"),
                Decimal("1.0002"),
            ),
            sleeper=lambda seconds: None,
        )
