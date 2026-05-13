import json
from decimal import Decimal

from stable_coin_trader.dashboard import build_dashboard_snapshot
from stable_coin_trader.models import MarketSnapshot
from stable_coin_trader.spread_observations import (
    append_spread_observations,
    build_spread_observations,
)


def make_snapshot(
    *,
    venue: str,
    bid: str,
    ask: str,
    observed_at: str = "2026-05-13T12:00:00Z",
) -> MarketSnapshot:
    return MarketSnapshot(
        venue=venue,
        symbol="USDC/EUR",
        bid=Decimal(bid),
        ask=Decimal(ask),
        bid_size=Decimal("2000"),
        ask_size=Decimal("2000"),
        observed_at=observed_at,
    )


def test_build_dashboard_snapshot_summarizes_observations_and_sampler_log(tmp_path):
    observations_path = tmp_path / "observations.jsonl"
    log_path = tmp_path / "sampler.log"
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
    append_spread_observations(observations_path, observations)
    log_path.write_text(
        "\n".join(
            [
                "sample=1 status=successful observations=2",
                "sample=2 status=failed observations=0 reason=temporary failure",
            ]
        ),
        encoding="utf-8",
    )

    snapshot = build_dashboard_snapshot(
        observations_path=observations_path,
        log_path=log_path,
        expected_samples=240,
    )

    assert snapshot["observation_count"] == 2
    assert snapshot["profitable_count"] == 1
    assert snapshot["sample_success_count"] == 1
    assert snapshot["sample_failure_count"] == 1
    assert snapshot["expected_samples"] == 240
    assert snapshot["completion_pct"] == "0.83"
    assert snapshot["best_route"] == "kraken->coinbase USDC/EUR"
    assert snapshot["best_edge_bps"] == "4.00160064"
    assert snapshot["average_edge_bps"] == "-1.99839984"
    assert snapshot["route_stats"][0]["route"] == "coinbase->kraken USDC/EUR"
    assert snapshot["route_stats"][1]["route"] == "kraken->coinbase USDC/EUR"
    assert len(snapshot["recent_observations"]) == 2
    assert json.dumps(snapshot)


def test_build_dashboard_snapshot_handles_missing_files(tmp_path):
    snapshot = build_dashboard_snapshot(
        observations_path=tmp_path / "missing.jsonl",
        log_path=tmp_path / "missing.log",
        expected_samples=None,
    )

    assert snapshot["observation_count"] == 0
    assert snapshot["profitable_count"] == 0
    assert snapshot["sample_success_count"] == 0
    assert snapshot["sample_failure_count"] == 0
    assert snapshot["completion_pct"] is None
    assert snapshot["route_stats"] == []
    assert snapshot["recent_observations"] == []
    assert snapshot["log_tail"] == []


def test_build_dashboard_snapshot_counts_all_samples_not_only_log_tail(tmp_path):
    observations_path = tmp_path / "observations.jsonl"
    log_path = tmp_path / "sampler.log"
    log_path.write_text(
        "\n".join(
            f"sample={sample_number} status=successful observations=2"
            for sample_number in range(1, 101)
        ),
        encoding="utf-8",
    )

    snapshot = build_dashboard_snapshot(
        observations_path=observations_path,
        log_path=log_path,
        expected_samples=100,
    )

    assert snapshot["sample_success_count"] == 100
    assert snapshot["sample_failure_count"] == 0
    assert snapshot["completed_samples"] == 100
    assert snapshot["completion_pct"] == "100"
    assert len(snapshot["log_tail"]) == 30
