from __future__ import annotations

import json
import os
from decimal import Decimal
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


def _normalized_path_string(path: Path) -> str:
    return os.path.normpath(os.fspath(path))


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
        if isinstance(value, (str, os.PathLike)):
            stripped = os.fspath(value).strip()
            if not stripped:
                raise ValueError("path cannot be blank")
            if os.path.normpath(stripped) == ".":
                raise ValueError("path cannot be the current directory")
            value = stripped

        return value

    @model_validator(mode="after")
    def validate_model_constraints(self) -> "BotConfig":
        if self.max_order_usd > self.max_position_usd:
            raise ValueError("max_order_usd cannot exceed max_position_usd")

        path_fields = (
            ("ledger_path", self.ledger_path),
            ("market_data_path", self.market_data_path),
            ("research_signals_path", self.research_signals_path),
        )
        seen_paths: dict[str, str] = {}
        for field_name, path in path_fields:
            normalized_path = _normalized_path_string(path)
            if normalized_path in seen_paths:
                raise ValueError(
                    f"{field_name} cannot overlap with {seen_paths[normalized_path]}"
                )
            seen_paths[normalized_path] = field_name

        return self


def load_config(path: str | os.PathLike[str]) -> BotConfig:
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    return BotConfig.model_validate(data)
