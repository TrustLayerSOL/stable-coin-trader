from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from stable_coin_trader.models import MarketSnapshot, parse_dt

JsonRequester = Callable[[str, dict[str, str]], Mapping[str, Any]]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CoinbaseProductMapping:
    product_id: str
    symbol: str


def parse_product_mapping(raw: str) -> CoinbaseProductMapping:
    parts = [part.strip() for part in raw.split(":", maxsplit=1)]
    if (
        len(parts) != 2
        or not parts[0]
        or not parts[1]
        or not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+", parts[0])
    ):
        raise ValueError("product mapping must use COINBASE_PRODUCT:BOT_SYMBOL")

    return CoinbaseProductMapping(product_id=parts[0], symbol=parts[1])


class CoinbasePublicMarketDataClient:
    def __init__(
        self,
        base_url: str = "https://api.exchange.coinbase.com",
        timeout_seconds: float = 10,
        requester: JsonRequester | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._requester = requester or self._request_json
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def fetch_order_book_snapshot(
        self,
        mapping: CoinbaseProductMapping,
    ) -> MarketSnapshot:
        payload = self._requester(
            f"/products/{mapping.product_id}/book",
            {"level": "1"},
        )
        asks = _require_book_side(payload, "asks")
        bids = _require_book_side(payload, "bids")
        best_ask = _parse_book_entry(asks[0], "ask")
        best_bid = _parse_book_entry(bids[0], "bid")

        return MarketSnapshot(
            venue="coinbase",
            symbol=mapping.symbol,
            bid=best_bid.price,
            ask=best_ask.price,
            bid_size=best_bid.size,
            ask_size=best_ask.size,
            observed_at=parse_dt(self._clock()),
        )

    def _request_json(self, path: str, params: dict[str, str]) -> Mapping[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        request = Request(
            url,
            headers={"User-Agent": "stable-coin-trader/0.1"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except (HTTPError, URLError) as exc:
            raise ConnectionError(f"Coinbase public request failed: {exc}") from exc

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Coinbase response was not valid JSON") from exc

        if not isinstance(payload, Mapping):
            raise ValueError("Coinbase response must be a JSON object")
        return payload


@dataclass(frozen=True)
class _BookEntry:
    price: Decimal
    size: Decimal


def _require_book_side(book: Mapping[str, Any], side: str) -> Sequence[Any]:
    values = book.get(side)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"Coinbase order book missing {side}")
    if not values:
        raise ValueError(f"Coinbase order book {side} is empty")
    return values


def _parse_book_entry(entry: Any, side: str) -> _BookEntry:
    if (
        not isinstance(entry, Sequence)
        or isinstance(entry, (str, bytes))
        or len(entry) < 2
    ):
        raise ValueError(f"Coinbase {side} order book entry is invalid")

    try:
        price = Decimal(str(entry[0]))
        size = Decimal(str(entry[1]))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Coinbase {side} order book entry is invalid") from exc

    return _BookEntry(price=price, size=size)
