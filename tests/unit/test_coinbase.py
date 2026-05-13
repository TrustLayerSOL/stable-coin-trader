from datetime import datetime, timezone
from decimal import Decimal

import pytest

from stable_coin_trader.coinbase import (
    CoinbasePublicMarketDataClient,
    parse_product_mapping,
)


def book_payload() -> dict[str, object]:
    return {
        "sequence": 13051505638,
        "bids": [["0.9998", "25000.5", 4]],
        "asks": [["1.0000", "18000.25", 2]],
        "time": "2026-05-13T13:00:00.000Z",
    }


def test_parse_product_mapping_splits_product_id_and_bot_symbol() -> None:
    mapping = parse_product_mapping(" USDC-EUR : USDC/EUR ")

    assert mapping.product_id == "USDC-EUR"
    assert mapping.symbol == "USDC/EUR"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        "USDC-EUR",
        ":USDC/EUR",
        "USDC-EUR:",
        "../accounts:USDC/EUR",
        "USDC/EUR:USDC/EUR",
        "USDC-EUR?level=3:USDC/EUR",
    ],
)
def test_parse_product_mapping_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="product"):
        parse_product_mapping(raw)


def test_coinbase_client_parses_public_level_one_book() -> None:
    requests: list[tuple[str, dict[str, str]]] = []
    observed_at = datetime(2026, 5, 13, 13, 6, tzinfo=timezone.utc)

    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        requests.append((path, params))
        return book_payload()

    client = CoinbasePublicMarketDataClient(
        requester=fake_request,
        clock=lambda: observed_at,
    )

    snapshot = client.fetch_order_book_snapshot(
        parse_product_mapping("USDC-EUR:USDC/EUR")
    )

    assert requests == [("/products/USDC-EUR/book", {"level": "1"})]
    assert snapshot.venue == "coinbase"
    assert snapshot.symbol == "USDC/EUR"
    assert snapshot.bid == Decimal("0.9998")
    assert snapshot.ask == Decimal("1.0000")
    assert snapshot.bid_size == Decimal("25000.5")
    assert snapshot.ask_size == Decimal("18000.25")
    assert snapshot.observed_at == observed_at


def test_coinbase_client_rejects_empty_order_book() -> None:
    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        return {"sequence": 1, "bids": [], "asks": [], "time": "2026-05-13T13:00:00Z"}

    client = CoinbasePublicMarketDataClient(requester=fake_request)

    with pytest.raises(ValueError, match="order book"):
        client.fetch_order_book_snapshot(parse_product_mapping("USDC-EUR:USDC/EUR"))


def test_coinbase_client_rejects_malformed_book_entry() -> None:
    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        return {"sequence": 1, "bids": [["bad"]], "asks": [["1.0", "1.0", 1]]}

    client = CoinbasePublicMarketDataClient(requester=fake_request)

    with pytest.raises(ValueError, match="bid"):
        client.fetch_order_book_snapshot(parse_product_mapping("USDC-EUR:USDC/EUR"))


def test_coinbase_client_rejects_malformed_numeric_book_entry() -> None:
    def fake_request(path: str, params: dict[str, str]) -> dict[str, object]:
        return {
            "sequence": 1,
            "bids": [["bad", "1.0", 1]],
            "asks": [["1.0", "1.0", 1]],
        }

    client = CoinbasePublicMarketDataClient(requester=fake_request)

    with pytest.raises(ValueError, match="bid"):
        client.fetch_order_book_snapshot(parse_product_mapping("USDC-EUR:USDC/EUR"))
