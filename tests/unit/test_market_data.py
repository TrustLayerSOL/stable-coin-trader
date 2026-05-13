import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from stable_coin_trader.market_data import load_market_snapshots


def test_load_market_snapshots_filters_symbol_and_venues(tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text(
        json.dumps(
            [
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "0.9999",
                    "ask": "1.0001",
                    "bid_size": "50000",
                    "ask_size": "50000",
                    "observed_at": "2026-05-13T12:00:00Z",
                },
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9995",
                    "ask": "0.9997",
                    "bid_size": "25000",
                    "ask_size": "25000",
                    "observed_at": "2026-05-13T12:00:00Z",
                },
                {
                    "venue": "gemini",
                    "symbol": "PYUSD/USD",
                    "bid": "0.9998",
                    "ask": "1.0000",
                    "bid_size": "10000",
                    "ask_size": "10000",
                    "observed_at": "2026-05-13T12:00:00Z",
                },
            ]
        )
    )

    snapshots = load_market_snapshots(
        path,
        symbols=["USDC/USD"],
        venues=["coinbase", "kraken"],
    )

    assert len(snapshots) == 2
    assert snapshots[0].venue == "coinbase"
    assert snapshots[1].ask == Decimal("0.9997")


def test_load_shipped_market_snapshots_fixture() -> None:
    path = "data/fixtures/market_snapshots.json"

    snapshots = load_market_snapshots(
        path,
        symbols=["USDC/USD"],
        venues=["coinbase", "kraken"],
    )

    assert [snapshot.venue for snapshot in snapshots] == ["coinbase", "kraken"]
    assert {snapshot.symbol for snapshot in snapshots} == {"USDC/USD"}


def test_load_market_snapshots_returns_empty_list_when_filters_do_not_match(
    tmp_path,
) -> None:
    path = tmp_path / "market.json"
    path.write_text(
        json.dumps(
            [
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "0.9999",
                    "ask": "1.0001",
                    "bid_size": "50000",
                    "ask_size": "50000",
                    "observed_at": "2026-05-13T12:00:00Z",
                }
            ]
        )
    )

    snapshots = load_market_snapshots(
        path,
        symbols=["PYUSD/USD"],
        venues=["kraken"],
    )

    assert snapshots == []


@pytest.mark.parametrize("path", ["", " ", ".", "./"])
def test_load_market_snapshots_rejects_unsafe_paths(path) -> None:
    with pytest.raises(ValueError, match="path"):
        load_market_snapshots(path, symbols=["USDC/USD"], venues=["coinbase"])


def test_load_market_snapshots_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_market_snapshots(
            tmp_path / "missing.json",
            symbols=["USDC/USD"],
            venues=["coinbase"],
        )


@pytest.mark.parametrize(
    ("symbols", "venues"),
    [
        ([], ["coinbase"]),
        ([" "], ["coinbase"]),
        (["USDC/USD"], []),
        (["USDC/USD"], [" "]),
    ],
)
def test_load_market_snapshots_rejects_empty_filters(symbols, venues, tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text("[]")

    with pytest.raises(ValueError, match="filter"):
        load_market_snapshots(path, symbols=symbols, venues=venues)


@pytest.mark.parametrize(
    ("symbols", "venues"),
    [
        ([object()], ["coinbase"]),
        (["USDC/USD"], [object()]),
        ("USDC/USD", ["coinbase"]),
        (["USDC/USD"], "coinbase"),
    ],
)
def test_load_market_snapshots_rejects_non_string_filters(
    symbols,
    venues,
    tmp_path,
) -> None:
    path = tmp_path / "market.json"
    path.write_text("[]")

    with pytest.raises(ValueError, match="filter"):
        load_market_snapshots(path, symbols=symbols, venues=venues)


def test_load_market_snapshots_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text("{")

    with pytest.raises(ValueError, match="valid JSON"):
        load_market_snapshots(path, symbols=["USDC/USD"], venues=["coinbase"])


def test_load_market_snapshots_rejects_non_list_json(tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text(json.dumps({"snapshots": []}))

    with pytest.raises(ValueError, match="list"):
        load_market_snapshots(path, symbols=["USDC/USD"], venues=["coinbase"])


def test_load_market_snapshots_rejects_invalid_snapshot(tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text(
        json.dumps(
            [
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "1.0002",
                    "ask": "1.0000",
                    "bid_size": "50000",
                    "ask_size": "50000",
                    "observed_at": "2026-05-13T12:00:00Z",
                }
            ]
        )
    )

    with pytest.raises(ValidationError):
        load_market_snapshots(path, symbols=["USDC/USD"], venues=["coinbase"])
