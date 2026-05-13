from __future__ import annotations

import sqlite3
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
    current_time = parse_dt(now or utc_now())

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
    signals = load_active_research_signals(config.research_signals_path)
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
        decisions = [
            risk.evaluate(
                trade=trade,
                opportunity=opportunity,
                signals=signals,
                current_position_usd=current_position_usd,
            )
            for trade in _trades_for_opportunity(opportunity)
        ]
        approved += sum(1 for decision in decisions if decision.approved)
        rejected += sum(1 for decision in decisions if not decision.approved)

        if not all(decision.approved for decision in decisions):
            for decision in decisions:
                ledger.record_risk_decision(decision)
            continue

        for decision in decisions:
            fill_id = executor.execute(decision)
            if fill_id is not None:
                fills += 1
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
    return [
        snapshot
        for snapshot in snapshots
        if (now - snapshot.observed_at).total_seconds() <= stale_after_seconds
    ]


def _current_position_usd(ledger: Ledger) -> Decimal:
    try:
        rows = ledger.fetch_all("select side, size, price from paper_fills")
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return Decimal("0")

    exposure = Decimal("0")
    for row in rows:
        notional = Decimal(row["size"]) * Decimal(row["price"])
        if row["side"] == "buy":
            exposure += notional
        elif row["side"] == "sell":
            exposure -= notional

    return max(exposure, Decimal("0"))
