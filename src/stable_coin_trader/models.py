from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MarketSnapshot(BaseModel):
    venue: str
    symbol: str
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
    id: str = Field(default_factory=lambda: str(uuid4()))
    buy_venue: str
    sell_venue: str
    symbol: str
    size: Decimal
    buy_price: Decimal
    sell_price: Decimal
    estimated_fees: Decimal
    estimated_slippage: Decimal
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
    opportunity_id: str
    side: Literal["buy", "sell"]
    venue: str
    symbol: str
    size: Decimal
    limit_price: Decimal


class ResearchSignal(BaseModel):
    id: str
    observed_at: datetime
    published_at: datetime
    source: str
    source_url: str
    source_quality: float = Field(ge=0, le=1)
    affected_assets: list[str]
    affected_venues: list[str]
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
    summary: str
    human_review_required: bool = False

    @field_validator("observed_at", "published_at", mode="before")
    @classmethod
    def parse_datetimes(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        current = parse_dt(current)
        age = current - self.observed_at
        return age.total_seconds() > self.ttl_seconds

    @property
    def risk_score(self) -> Decimal:
        return Decimal(str(self.severity * self.confidence * self.source_quality))


class RiskDecision(BaseModel):
    trade: ProposedTrade
    approved: bool
    reason: str
    min_edge_bps: Decimal = Decimal("0")
    requires_human_approval: bool = False
    active_signal_ids: list[str] = Field(default_factory=list)

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
