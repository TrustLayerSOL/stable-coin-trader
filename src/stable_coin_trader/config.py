from __future__ import annotations

import json
from decimal import Decimal
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class BotConfig(BaseModel):
    mode: Literal["paper"]
    ledger_path: Path
    market_data_path: Path
    research_signals_path: Path
    base_currency: NonEmptyString = "USD"
    symbols: list[NonEmptyString] = Field(min_length=1)
    venues: list[NonEmptyString] = Field(min_length=1)
    max_order_usd: Decimal = Field(gt=0)
    max_position_usd: Decimal = Field(gt=0)
    min_edge_bps: Decimal = Field(ge=0)
    stale_after_seconds: int = Field(gt=0)
    depeg_threshold_bps: Decimal = Field(gt=0)
    daily_loss_limit_usd: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_order_limit(self) -> "BotConfig":
        if self.max_order_usd > self.max_position_usd:
            raise ValueError("max_order_usd cannot exceed max_position_usd")
        return self


def load_config(path: str | PathLike[str]) -> BotConfig:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return BotConfig(**data)
