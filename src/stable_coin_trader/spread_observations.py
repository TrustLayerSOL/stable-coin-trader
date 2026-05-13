from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from stable_coin_trader.models import (
    MarketSnapshot,
    NonEmptyString,
    decimal_key,
    parse_dt,
)
from stable_coin_trader.opportunities import bps_cost


class SpreadObservation(BaseModel):
    id: NonEmptyString
    symbol: NonEmptyString
    buy_venue: NonEmptyString
    sell_venue: NonEmptyString
    requested_size: Decimal = Field(gt=0)
    size: Decimal = Field(gt=0)
    buy_price: Decimal = Field(gt=0)
    sell_price: Decimal = Field(gt=0)
    buy_notional: Decimal = Field(gt=0)
    sell_notional: Decimal = Field(gt=0)
    gross_profit: Decimal
    estimated_fees: Decimal = Field(ge=0)
    estimated_slippage: Decimal = Field(ge=0)
    net_profit: Decimal
    net_edge_bps: Decimal
    snapshot_lag_seconds: Decimal = Field(ge=0)
    buy_observed_at: datetime
    sell_observed_at: datetime
    observed_at: datetime

    @field_validator(
        "buy_observed_at",
        "sell_observed_at",
        "observed_at",
        mode="before",
    )
    @classmethod
    def parse_datetimes(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > 0

    @property
    def route(self) -> str:
        return f"{self.buy_venue}->{self.sell_venue} {self.symbol}"


class SpreadObservationSummary(BaseModel):
    observation_count: int = Field(ge=0)
    profitable_count: int = Field(ge=0)
    best_observation_id: str | None = None
    best_route: str | None = None
    best_net_profit: Decimal | None = None
    best_net_edge_bps: Decimal | None = None
    average_net_profit: Decimal | None = None
    average_net_edge_bps: Decimal | None = None
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None


def build_spread_observations(
    snapshots: list[MarketSnapshot],
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    max_snapshot_lag_seconds: Decimal,
) -> list[SpreadObservation]:
    _validate_inputs(
        size=size,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        max_snapshot_lag_seconds=max_snapshot_lag_seconds,
    )

    by_symbol: dict[str, list[MarketSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_symbol[snapshot.symbol].append(snapshot)

    observations: list[SpreadObservation] = []
    for symbol, symbol_snapshots in by_symbol.items():
        for buy in symbol_snapshots:
            for sell in symbol_snapshots:
                if buy.venue == sell.venue:
                    continue

                snapshot_lag_seconds = _snapshot_lag_seconds(
                    buy.observed_at,
                    sell.observed_at,
                )
                if snapshot_lag_seconds > max_snapshot_lag_seconds:
                    continue

                executable_size = min(size, buy.ask_size, sell.bid_size)
                if executable_size <= 0:
                    continue

                buy_notional = buy.ask * executable_size
                sell_notional = sell.bid * executable_size
                gross_profit = (sell.bid - buy.ask) * executable_size
                estimated_fees = bps_cost(buy_notional + sell_notional, fee_bps)
                estimated_slippage = bps_cost(
                    buy_notional + sell_notional,
                    slippage_bps,
                )
                net_profit = gross_profit - estimated_fees - estimated_slippage
                net_edge_bps = (net_profit / buy_notional) * Decimal("10000")
                observed_at = max(buy.observed_at, sell.observed_at)
                observations.append(
                    SpreadObservation(
                        id=_stable_observation_id(
                            symbol=symbol,
                            buy=buy,
                            sell=sell,
                            requested_size=size,
                            executable_size=executable_size,
                            fee_bps=fee_bps,
                            slippage_bps=slippage_bps,
                        ),
                        symbol=symbol,
                        buy_venue=buy.venue,
                        sell_venue=sell.venue,
                        requested_size=size,
                        size=executable_size,
                        buy_price=buy.ask,
                        sell_price=sell.bid,
                        buy_notional=buy_notional,
                        sell_notional=sell_notional,
                        gross_profit=gross_profit,
                        estimated_fees=estimated_fees,
                        estimated_slippage=estimated_slippage,
                        net_profit=net_profit,
                        net_edge_bps=net_edge_bps,
                        snapshot_lag_seconds=snapshot_lag_seconds,
                        buy_observed_at=buy.observed_at,
                        sell_observed_at=sell.observed_at,
                        observed_at=observed_at,
                    )
                )

    return sorted(
        observations,
        key=lambda item: (
            -item.net_profit,
            -item.net_edge_bps,
            item.symbol,
            item.buy_venue,
            item.sell_venue,
            item.buy_price,
            item.sell_price,
            item.size,
            item.observed_at,
        ),
    )


def append_spread_observations(
    path: str | os.PathLike[str],
    observations: list[SpreadObservation],
) -> None:
    output_path = _observation_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not observations:
        output_path.touch(exist_ok=True)
        return

    with output_path.open("a", encoding="utf-8") as output_file:
        for observation in observations:
            output_file.write(json.dumps(_observation_json(observation)) + "\n")


def load_spread_observations(
    path: str | os.PathLike[str],
) -> list[SpreadObservation]:
    input_path = _observation_path(path)
    observations: list[SpreadObservation] = []
    for line_number, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"spread observation JSONL line {line_number} must contain valid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"spread observation JSONL line {line_number} must be a JSON object"
            )
        try:
            observations.append(SpreadObservation.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"spread observation JSONL line {line_number} is malformed"
            ) from exc
    return observations


def summarize_spread_observations(
    observations: list[SpreadObservation],
) -> SpreadObservationSummary:
    if not observations:
        return SpreadObservationSummary(
            observation_count=0,
            profitable_count=0,
        )

    ordered = sorted(
        observations,
        key=lambda item: (
            -item.net_profit,
            -item.net_edge_bps,
            item.symbol,
            item.buy_venue,
            item.sell_venue,
            item.observed_at,
        ),
    )
    best = ordered[0]
    observation_count = len(observations)
    return SpreadObservationSummary(
        observation_count=observation_count,
        profitable_count=sum(
            1 for observation in observations if observation.is_profitable
        ),
        best_observation_id=best.id,
        best_route=best.route,
        best_net_profit=best.net_profit,
        best_net_edge_bps=best.net_edge_bps,
        average_net_profit=sum(
            (observation.net_profit for observation in observations),
            Decimal("0"),
        )
        / observation_count,
        average_net_edge_bps=sum(
            (observation.net_edge_bps for observation in observations),
            Decimal("0"),
        )
        / observation_count,
        first_observed_at=min(observation.observed_at for observation in observations),
        last_observed_at=max(observation.observed_at for observation in observations),
    )


def _validate_inputs(
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
    max_snapshot_lag_seconds: Decimal,
) -> None:
    if not size.is_finite():
        raise ValueError("size must be finite")
    if size <= 0:
        raise ValueError("size must be positive")

    for name, value in (
        ("fee_bps", fee_bps),
        ("slippage_bps", slippage_bps),
        ("max_snapshot_lag_seconds", max_snapshot_lag_seconds),
    ):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")


def _snapshot_lag_seconds(first: datetime, second: datetime) -> Decimal:
    delta = abs(parse_dt(first) - parse_dt(second))
    whole_seconds = delta.days * 86400 + delta.seconds
    return Decimal(whole_seconds) + (
        Decimal(delta.microseconds) / Decimal("1000000")
    )


def _stable_observation_id(
    symbol: str,
    buy: MarketSnapshot,
    sell: MarketSnapshot,
    requested_size: Decimal,
    executable_size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> str:
    raw = "|".join(
        (
            "spread-observation",
            symbol,
            buy.venue,
            sell.venue,
            decimal_key(requested_size),
            decimal_key(executable_size),
            decimal_key(buy.ask),
            decimal_key(sell.bid),
            decimal_key(fee_bps),
            decimal_key(slippage_bps),
            parse_dt(buy.observed_at).isoformat(),
            parse_dt(sell.observed_at).isoformat(),
        )
    )
    return f"spread-observation-{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _observation_path(path: str | os.PathLike[str]) -> Path:
    raw_path = os.fspath(path).strip()
    if not raw_path:
        raise ValueError("spread observation path cannot be blank")
    if os.path.normpath(raw_path) == ".":
        raise ValueError("spread observation path cannot be the current directory")

    observation_path = Path(raw_path)
    if observation_path.is_dir():
        raise ValueError("spread observation path must be a file")
    return observation_path


def _observation_json(observation: SpreadObservation) -> dict[str, Any]:
    return {
        "id": observation.id,
        "symbol": observation.symbol,
        "buy_venue": observation.buy_venue,
        "sell_venue": observation.sell_venue,
        "requested_size": str(observation.requested_size),
        "size": str(observation.size),
        "buy_price": str(observation.buy_price),
        "sell_price": str(observation.sell_price),
        "buy_notional": str(observation.buy_notional),
        "sell_notional": str(observation.sell_notional),
        "gross_profit": str(observation.gross_profit),
        "estimated_fees": str(observation.estimated_fees),
        "estimated_slippage": str(observation.estimated_slippage),
        "net_profit": str(observation.net_profit),
        "net_edge_bps": str(observation.net_edge_bps),
        "snapshot_lag_seconds": str(observation.snapshot_lag_seconds),
        "buy_observed_at": _format_datetime(observation.buy_observed_at),
        "sell_observed_at": _format_datetime(observation.sell_observed_at),
        "observed_at": _format_datetime(observation.observed_at),
        "profitable": observation.is_profitable,
    }


def _format_datetime(value: datetime) -> str:
    return parse_dt(value).isoformat().replace("+00:00", "Z")
