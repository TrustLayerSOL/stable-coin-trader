import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from stable_coin_trader.kraken import (
    KrakenPublicMarketDataClient,
    parse_pair_mapping,
    write_market_snapshots,
)


def depth_payload() -> dict[str, object]:
    return {
        "error": [],
        "result": {
            "USDCUSD": {
                "asks": [["1.00010", "1234.5", 1778677201]],
                "bids": [["0.99990", "2345.6", 1778677200]],
            }
        },
    }


def test_parse_pair_mapping_splits_kraken_pair_and_bot_symbol() -> None:
    mapping = parse_pair_mapping(" USDCUSD : USDC/USD ")

    assert mapping.kraken_pair == "USDCUSD"
    assert mapping.symbol == "USDC/USD"


@pytest.mark.parametrize("raw", ["", " ", "USDCUSD", ":USDC/USD", "USDCUSD:"])
def test_parse_pair_mapping_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="pair"):
        parse_pair_mapping(raw)


def test_kraken_client_parses_public_depth_top_of_book() -> None:
    requests: list[tuple[str, dict[str, str]]] = []
    observed_at = datetime(2026, 5, 13, 13, 5, tzinfo=timezone.utc)

    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        requests.append((path, params))
        return depth_payload()

    client = KrakenPublicMarketDataClient(
        requester=fake_request,
        clock=lambda: observed_at,
    )

    snapshot = client.fetch_order_book_snapshot(parse_pair_mapping("USDCUSD:USDC/USD"))

    assert requests == [("/0/public/Depth", {"pair": "USDCUSD", "count": "1"})]
    assert snapshot.venue == "kraken"
    assert snapshot.symbol == "USDC/USD"
    assert snapshot.bid == Decimal("0.99990")
    assert snapshot.ask == Decimal("1.00010")
    assert snapshot.bid_size == Decimal("2345.6")
    assert snapshot.ask_size == Decimal("1234.5")
    assert snapshot.observed_at == observed_at


def test_kraken_client_raises_on_api_error() -> None:
    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        return {"error": ["EQuery:Unknown asset pair"], "result": {}}

    client = KrakenPublicMarketDataClient(requester=fake_request)

    with pytest.raises(ValueError, match="Kraken API error"):
        client.fetch_order_book_snapshot(parse_pair_mapping("BADPAIR:USDC/USD"))


def test_kraken_client_rejects_empty_order_book() -> None:
    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        return {
            "error": [],
            "result": {"USDCUSD": {"asks": [], "bids": []}},
        }

    client = KrakenPublicMarketDataClient(requester=fake_request)

    with pytest.raises(ValueError, match="order book"):
        client.fetch_order_book_snapshot(parse_pair_mapping("USDCUSD:USDC/USD"))


def test_write_market_snapshots_writes_fixture_shaped_json(tmp_path) -> None:
    observed_at = datetime(2026, 5, 13, 13, 5, tzinfo=timezone.utc)
    client = KrakenPublicMarketDataClient(
        requester=lambda path, params: depth_payload(),
        clock=lambda: observed_at,
    )
    snapshot = client.fetch_order_book_snapshot(parse_pair_mapping("USDCUSD:USDC/USD"))
    output = tmp_path / "kraken_snapshots.json"

    write_market_snapshots(output, [snapshot])

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data == [
        {
            "venue": "kraken",
            "symbol": "USDC/USD",
            "bid": "0.99990",
            "ask": "1.00010",
            "bid_size": "2345.6",
            "ask_size": "1234.5",
            "observed_at": "2026-05-13T13:05:00Z",
        }
    ]
