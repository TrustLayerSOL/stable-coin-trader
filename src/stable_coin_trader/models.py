from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        parsed = datetime.fromisoformat(value)
    else:
        raise ValueError("expected datetime or ISO datetime string")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def decimal_key(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


class MarketSnapshot(BaseModel):
    venue: NonEmptyString
    symbol: NonEmptyString
    bid: Decimal
    ask: Decimal
    bid_size: Decimal
    ask_size: Decimal
    observed_at: datetime

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_at(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @model_validator(mode="after")
    def validate_book(self) -> "MarketSnapshot":
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.bid > self.ask:
            raise ValueError("bid cannot be greater than ask")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("book sizes cannot be negative")
        return self

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


class Opportunity(BaseModel):
    id: NonEmptyString = Field(default_factory=lambda: str(uuid4()))
    buy_venue: NonEmptyString
    sell_venue: NonEmptyString
    symbol: NonEmptyString
    size: Decimal = Field(gt=0)
    buy_price: Decimal = Field(gt=0)
    sell_price: Decimal = Field(gt=0)
    estimated_fees: Decimal = Field(ge=0)
    estimated_slippage: Decimal = Field(ge=0)
    observed_at: datetime

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_at(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @property
    def gross_profit(self) -> Decimal:
        return (self.sell_price - self.buy_price) * self.size

    @property
    def net_profit(self) -> Decimal:
        return self.gross_profit - self.estimated_fees - self.estimated_slippage

    @property
    def notional(self) -> Decimal:
        return self.buy_price * self.size

    @property
    def net_edge_bps(self) -> Decimal:
        if self.notional <= 0:
            return Decimal("0")
        return (self.net_profit / self.notional) * Decimal("10000")


class ProposedTrade(BaseModel):
    opportunity_id: NonEmptyString
    side: Literal["buy", "sell"]
    venue: NonEmptyString
    symbol: NonEmptyString
    size: Decimal = Field(gt=0)
    limit_price: Decimal = Field(gt=0)


class ResearchSignal(BaseModel):
    id: NonEmptyString
    observed_at: datetime
    published_at: datetime
    source: NonEmptyString
    source_url: NonEmptyString
    source_quality: float = Field(ge=0, le=1)
    affected_assets: list[NonEmptyString]
    affected_venues: list[NonEmptyString]
    event_type: Literal[
        "depeg_risk",
        "issuer_reserve",
        "issuer_redemption",
        "venue_outage",
        "withdrawal_delay",
        "regulatory",
        "macro",
        "liquidity",
        "oracle",
        "rumor",
        "social_trend",
        "informational",
    ]
    direction: Literal["risk_increase", "risk_decrease", "neutral"]
    severity: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    ttl_seconds: int = Field(gt=0)
    summary: NonEmptyString
    human_review_required: bool = False

    @field_validator("observed_at", "published_at", mode="before")
    @classmethod
    def parse_datetimes(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @model_validator(mode="after")
    def validate_timeline(self) -> "ResearchSignal":
        if self.published_at > self.observed_at:
            raise ValueError("published_at cannot be after observed_at")
        return self

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        current = parse_dt(current)
        age = current - self.observed_at
        age_seconds = age.total_seconds()
        return age_seconds < 0 or age_seconds > self.ttl_seconds

    @property
    def risk_score(self) -> Decimal:
        return (
            Decimal(str(self.severity))
            * Decimal(str(self.confidence))
            * Decimal(str(self.source_quality))
        )


class RiskDecision(BaseModel):
    trade: ProposedTrade
    approved: bool
    reason: NonEmptyString
    min_edge_bps: Decimal = Field(default=Decimal("0"), ge=0)
    requires_human_approval: bool = False
    active_signal_ids: list[NonEmptyString] = Field(default_factory=list)

    @classmethod
    def approve(
        cls,
        trade: ProposedTrade,
        reason: str,
        min_edge_bps: Decimal,
        active_signal_ids: list[str] | None = None,
    ) -> "RiskDecision":
        return cls(
            trade=trade,
            approved=True,
            reason=reason,
            min_edge_bps=min_edge_bps,
            active_signal_ids=active_signal_ids or [],
        )

    @classmethod
    def reject(
        cls,
        trade: ProposedTrade,
        reason: str,
        min_edge_bps: Decimal = Decimal("0"),
        requires_human_approval: bool = False,
        active_signal_ids: list[str] | None = None,
    ) -> "RiskDecision":
        return cls(
            trade=trade,
            approved=False,
            reason=reason,
            min_edge_bps=min_edge_bps,
            requires_human_approval=requires_human_approval,
            active_signal_ids=active_signal_ids or [],
        )
