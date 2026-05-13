from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from time import sleep

from pydantic import BaseModel, Field

from stable_coin_trader.coinbase import (
    CoinbaseProductMapping,
    CoinbasePublicMarketDataClient,
)
from stable_coin_trader.kraken import KrakenPairMapping, KrakenPublicMarketDataClient
from stable_coin_trader.models import MarketSnapshot, NonEmptyString
from stable_coin_trader.spread_observations import (
    SpreadObservationSummary,
    append_spread_observations,
    build_spread_observations,
    summarize_spread_observations,
)

Sleeper = Callable[[float], None]
SampleProgress = Callable[[int, bool, int, str | None], None]


class SpreadSampleFailure(BaseModel):
    sample_number: int = Field(gt=0)
    reason: NonEmptyString


class SpreadSamplingResult(BaseModel):
    samples_requested: int = Field(gt=0)
    samples_successful: int = Field(ge=0)
    samples_failed: int = Field(ge=0)
    observations_written: int = Field(ge=0)
    failures: list[SpreadSampleFailure] = Field(default_factory=list)
    summary: SpreadObservationSummary


def sample_spreads(
    kraken_mappings: Sequence[KrakenPairMapping],
    coinbase_mappings: Sequence[CoinbaseProductMapping],
    output_path: str | Path,
    samples: int,
    interval_seconds: Decimal,
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    max_snapshot_lag_seconds: Decimal,
    kraken_client: KrakenPublicMarketDataClient | None = None,
    coinbase_client: CoinbasePublicMarketDataClient | None = None,
    sleeper: Sleeper = sleep,
    on_sample_result: SampleProgress | None = None,
) -> SpreadSamplingResult:
    _validate_sampling_inputs(
        kraken_mappings=kraken_mappings,
        coinbase_mappings=coinbase_mappings,
        samples=samples,
        interval_seconds=interval_seconds,
        size=size,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        max_snapshot_lag_seconds=max_snapshot_lag_seconds,
    )

    kraken = kraken_client or KrakenPublicMarketDataClient()
    coinbase = coinbase_client or CoinbasePublicMarketDataClient()
    failures: list[SpreadSampleFailure] = []
    all_observations = []

    for sample_number in range(1, samples + 1):
        try:
            snapshots = _fetch_sample_snapshots(
                kraken_mappings=kraken_mappings,
                coinbase_mappings=coinbase_mappings,
                kraken_client=kraken,
                coinbase_client=coinbase,
            )
            observations = build_spread_observations(
                snapshots=snapshots,
                size=size,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                max_snapshot_lag_seconds=max_snapshot_lag_seconds,
            )
            append_spread_observations(output_path, observations)
            all_observations.extend(observations)
            if on_sample_result is not None:
                on_sample_result(sample_number, True, len(observations), None)
        except (ConnectionError, ValueError) as exc:
            reason = str(exc)
            failures.append(
                SpreadSampleFailure(
                    sample_number=sample_number,
                    reason=reason,
                )
            )
            if on_sample_result is not None:
                on_sample_result(sample_number, False, 0, reason)

        if sample_number < samples:
            sleeper(float(interval_seconds))

    return SpreadSamplingResult(
        samples_requested=samples,
        samples_successful=samples - len(failures),
        samples_failed=len(failures),
        observations_written=len(all_observations),
        failures=failures,
        summary=summarize_spread_observations(all_observations),
    )


def _fetch_sample_snapshots(
    kraken_mappings: Sequence[KrakenPairMapping],
    coinbase_mappings: Sequence[CoinbaseProductMapping],
    kraken_client: KrakenPublicMarketDataClient,
    coinbase_client: CoinbasePublicMarketDataClient,
) -> list[MarketSnapshot]:
    snapshots = [
        kraken_client.fetch_order_book_snapshot(mapping)
        for mapping in kraken_mappings
    ]
    snapshots.extend(
        coinbase_client.fetch_order_book_snapshot(mapping)
        for mapping in coinbase_mappings
    )
    return snapshots


def _validate_sampling_inputs(
    kraken_mappings: Sequence[KrakenPairMapping],
    coinbase_mappings: Sequence[CoinbaseProductMapping],
    samples: int,
    interval_seconds: Decimal,
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    max_snapshot_lag_seconds: Decimal,
) -> None:
    if not kraken_mappings and not coinbase_mappings:
        raise ValueError("at least one public market-data mapping is required")
    if samples <= 0:
        raise ValueError("samples must be positive")

    if not size.is_finite():
        raise ValueError("size must be finite")
    if size <= 0:
        raise ValueError("size must be positive")

    for name, value in (
        ("interval_seconds", interval_seconds),
        ("fee_bps", fee_bps),
        ("slippage_bps", slippage_bps),
        ("max_snapshot_lag_seconds", max_snapshot_lag_seconds),
    ):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")

    if interval_seconds > Decimal(str(sys.float_info.max)):
        raise ValueError("interval_seconds is too large")
