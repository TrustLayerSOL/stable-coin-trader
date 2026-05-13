from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from stable_coin_trader.config import BotConfig
from stable_coin_trader.ledger import Ledger
from stable_coin_trader.market_data import load_market_snapshots
from stable_coin_trader.models import (
    MarketSnapshot,
    Opportunity,
    ProposedTrade,
    parse_dt,
    utc_now,
)
from stable_coin_trader.opportunities import find_spread_opportunities
from stable_coin_trader.paper import PaperExecutor
from stable_coin_trader.research import load_active_research_signals
from stable_coin_trader.risk import RiskEngine


class EngineRunResult(BaseModel):
    opportunities_seen: int
    approved_trades: int
    rejected_trades: int
    paper_fills: int


def run_once(config: BotConfig, now: datetime | None = None) -> EngineRunResult:
    ledger = Ledger(config.ledger_path)
    ledger.initialize()
    current_time = parse_dt(now or config.run_as_of or utc_now())

    snapshots = load_market_snapshots(
        config.market_data_path,
        symbols=config.symbols,
        venues=config.venues,
    )
    snapshots = _fresh_snapshots(
        snapshots=snapshots,
        now=current_time,
        stale_after_seconds=config.stale_after_seconds,
    )
    signals = load_active_research_signals(config.research_signals_path, now=current_time)
    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=config.max_order_usd,
        fee_bps=config.fee_bps,
        slippage_bps=config.slippage_bps,
    )

    risk = RiskEngine(config)
    executor = PaperExecutor(ledger=ledger, fee_bps=config.fee_bps)

    approved = 0
    rejected = 0
    fills = 0
    current_position_usd = _current_position_usd(ledger)

    for opportunity in opportunities:
        if _opportunity_already_filled(ledger, opportunity):
            continue

        decisions = [
            risk.evaluate(
                trade=trade,
                opportunity=opportunity,
                signals=signals,
                current_position_usd=current_position_usd,
            )
            for trade in _trades_for_opportunity(opportunity)
        ]
        if not all(decision.approved for decision in decisions):
            approved += sum(1 for decision in decisions if decision.approved)
            rejected += sum(1 for decision in decisions if not decision.approved)
            for decision in decisions:
                ledger.record_risk_decision(decision, created_at=current_time)
            continue

        fill_ids = executor.execute_many(decisions, created_at=current_time)
        if not fill_ids:
            continue

        approved += len(decisions)
        fills += len(fill_ids)
        current_position_usd = _current_position_usd(ledger)

    return EngineRunResult(
        opportunities_seen=len(opportunities),
        approved_trades=approved,
        rejected_trades=rejected,
        paper_fills=fills,
    )


def _trades_for_opportunity(opportunity: Opportunity) -> list[ProposedTrade]:
    return [
        ProposedTrade(
            opportunity_id=opportunity.id,
            side="buy",
            venue=opportunity.buy_venue,
            symbol=opportunity.symbol,
            size=opportunity.size,
            limit_price=opportunity.buy_price,
        ),
        ProposedTrade(
            opportunity_id=opportunity.id,
            side="sell",
            venue=opportunity.sell_venue,
            symbol=opportunity.symbol,
            size=opportunity.size,
            limit_price=opportunity.sell_price,
        ),
    ]


def _fresh_snapshots(
    snapshots: list[MarketSnapshot],
    now: datetime,
    stale_after_seconds: int,
) -> list[MarketSnapshot]:
    fresh: list[MarketSnapshot] = []
    for snapshot in snapshots:
        age_seconds = (now - snapshot.observed_at).total_seconds()
        if 0 <= age_seconds <= stale_after_seconds:
            fresh.append(snapshot)
    return fresh


def _current_position_usd(ledger: Ledger) -> Decimal:
    rows = ledger.fetch_all("select side, size, price from paper_fills")
    exposure = Decimal("0")
    for row in rows:
        notional = Decimal(row["size"]) * Decimal(row["price"])
        if row["side"] == "buy":
            exposure += notional
        elif row["side"] == "sell":
            exposure -= notional

    return max(exposure, Decimal("0"))


def _opportunity_already_filled(ledger: Ledger, opportunity: Opportunity) -> bool:
    return ledger.has_paper_fill_for_opportunity(opportunity.id)
