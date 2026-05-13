from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from stable_coin_trader.models import MarketSnapshot, parse_dt

JsonRequester = Callable[[str, dict[str, str]], Mapping[str, Any]]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class KrakenPairMapping:
    kraken_pair: str
    symbol: str


def parse_pair_mapping(raw: str) -> KrakenPairMapping:
    parts = [part.strip() for part in raw.split(":", maxsplit=1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("pair mapping must use KRAKEN_PAIR:BOT_SYMBOL")

    return KrakenPairMapping(kraken_pair=parts[0], symbol=parts[1])


class KrakenPublicMarketDataClient:
    def __init__(
        self,
        base_url: str = "https://api.kraken.com",
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
        mapping: KrakenPairMapping,
        count: int = 1,
    ) -> MarketSnapshot:
        if count <= 0:
            raise ValueError("Kraken order book count must be positive")

        payload = self._requester(
            "/0/public/Depth",
            {"pair": mapping.kraken_pair, "count": str(count)},
        )
        errors = payload.get("error")
        if errors:
            raise ValueError(f"Kraken API error: {', '.join(str(error) for error in errors)}")

        book = _extract_single_order_book(payload)
        asks = _require_book_side(book, "asks")
        bids = _require_book_side(book, "bids")
        best_ask = _parse_book_entry(asks[0], "ask")
        best_bid = _parse_book_entry(bids[0], "bid")

        return MarketSnapshot(
            venue="kraken",
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
            raise ConnectionError(f"Kraken public request failed: {exc}") from exc

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Kraken response was not valid JSON") from exc

        if not isinstance(payload, Mapping):
            raise ValueError("Kraken response must be a JSON object")
        return payload


@dataclass(frozen=True)
class _BookEntry:
    price: Decimal
    size: Decimal
    observed_at: datetime


def _extract_single_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result = payload.get("result")
    if not isinstance(result, Mapping) or not result:
        raise ValueError("Kraken order book response missing result")
    if len(result) != 1:
        raise ValueError("Kraken order book response must contain one pair result")

    book = next(iter(result.values()))
    if not isinstance(book, Mapping):
        raise ValueError("Kraken order book result must be an object")
    return book


def _require_book_side(book: Mapping[str, Any], side: str) -> Sequence[Any]:
    values = book.get(side)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"Kraken order book missing {side}")
    if not values:
        raise ValueError(f"Kraken order book {side} is empty")
    return values


def _parse_book_entry(entry: Any, side: str) -> _BookEntry:
    if (
        not isinstance(entry, Sequence)
        or isinstance(entry, (str, bytes))
        or len(entry) < 3
    ):
        raise ValueError(f"Kraken {side} order book entry is invalid")

    try:
        price = Decimal(str(entry[0]))
        size = Decimal(str(entry[1]))
        observed_at = datetime.fromtimestamp(float(entry[2]), timezone.utc)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Kraken {side} order book entry is invalid") from exc

    return _BookEntry(price=price, size=size, observed_at=observed_at)


def write_market_snapshots(path: str | Path, snapshots: list[MarketSnapshot]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([_snapshot_json(snapshot) for snapshot in snapshots], indent=2)
        + "\n",
        encoding="utf-8",
    )


def _snapshot_json(snapshot: MarketSnapshot) -> dict[str, str]:
    observed_at = parse_dt(snapshot.observed_at).isoformat().replace("+00:00", "Z")
    return {
        "venue": snapshot.venue,
        "symbol": snapshot.symbol,
        "bid": str(snapshot.bid),
        "ask": str(snapshot.ask),
        "bid_size": str(snapshot.bid_size),
        "ask_size": str(snapshot.ask_size),
        "observed_at": observed_at,
    }
