from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from stable_coin_trader.models import parse_dt
from stable_coin_trader.models import MarketSnapshot


def _market_data_path(path: str | os.PathLike[str]) -> Path:
    raw_path = os.fspath(path).strip()
    if not raw_path:
        raise ValueError("market data path cannot be blank")
    if os.path.normpath(raw_path) == ".":
        raise ValueError("market data path cannot be the current directory")

    market_data_path = Path(raw_path)
    if market_data_path.is_dir():
        raise ValueError("market data path must be a file")
    return market_data_path


def _filter_values(name: str, values: Iterable[str]) -> set[str]:
    if isinstance(values, str):
        raise ValueError(f"{name} filter must be a list of strings")

    normalized_values: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{name} filter values must be strings")
        stripped_value = value.strip()
        if stripped_value:
            normalized_values.add(stripped_value)

    if not normalized_values:
        raise ValueError(f"{name} filter cannot be empty")
    return normalized_values


def _load_json_list(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("market snapshot fixture must contain valid JSON") from exc

    if not isinstance(data, list):
        raise ValueError("market snapshot fixture must be a JSON list")
    return data


def load_market_snapshots(
    path: str | Path,
    symbols: list[str],
    venues: list[str],
) -> list[MarketSnapshot]:
    symbol_set = _filter_values("symbols", symbols)
    venue_set = _filter_values("venues", venues)
    data = _load_json_list(_market_data_path(path))
    snapshots = [MarketSnapshot.model_validate(item) for item in data]

    return [
        snapshot
        for snapshot in snapshots
        if snapshot.symbol in symbol_set and snapshot.venue in venue_set
    ]


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
