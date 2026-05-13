from __future__ import annotations

import json
from decimal import Decimal
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class BotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    stale_after_seconds: int = Field(gt=0, strict=True)
    depeg_threshold_bps: Decimal = Field(gt=0)
    daily_loss_limit_usd: Decimal = Field(gt=0)

    @field_validator(
        "ledger_path",
        "market_data_path",
        "research_signals_path",
        mode="before",
    )
    @classmethod
    def validate_non_blank_path(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("path cannot be blank")
            if Path(stripped) == Path("."):
                raise ValueError("path cannot be the current directory")
            value = stripped

        if isinstance(value, PathLike) and Path(value) == Path("."):
            raise ValueError("path cannot be the current directory")

        return value

    @model_validator(mode="after")
    def validate_order_limit(self) -> "BotConfig":
        if self.max_order_usd > self.max_position_usd:
            raise ValueError("max_order_usd cannot exceed max_position_usd")
        return self


def load_config(path: str | PathLike[str]) -> BotConfig:
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    return BotConfig.model_validate(data)
