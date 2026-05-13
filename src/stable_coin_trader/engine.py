from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from stable_coin_trader.config import BotConfig
from stable_coin_trader.ledger import Ledger
from stable_coin_trader.market_data import load_market_snapshots
from stable_coin_trader.models import Opportunity, ProposedTrade
from stable_coin_trader.opportunities import find_spread_opportunities
from stable_coin_trader.paper import PaperExecutor
from stable_coin_trader.research import load_active_research_signals
from stable_coin_trader.risk import RiskEngine


class EngineRunResult(BaseModel):
    opportunities_seen: int
    approved_trades: int
    rejected_trades: int
    paper_fills: int


def run_once(config: BotConfig) -> EngineRunResult:
    ledger = Ledger(config.ledger_path)
    ledger.initialize()

    snapshots = load_market_snapshots(
        config.market_data_path,
        symbols=config.symbols,
        venues=config.venues,
    )
    signals = load_active_research_signals(config.research_signals_path)
    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=config.max_order_usd,
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    risk = RiskEngine(config)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))

    approved = 0
    rejected = 0
    fills = 0
    current_position_usd = Decimal("0")

    for opportunity in opportunities:
        for trade in _trades_for_opportunity(opportunity):
            decision = risk.evaluate(
                trade=trade,
                opportunity=opportunity,
                signals=signals,
                current_position_usd=current_position_usd,
            )
            if decision.approved:
                approved += 1
            else:
                rejected += 1

            fill_id = executor.execute(decision)
            if fill_id is not None:
                fills += 1
                current_position_usd += trade.size * trade.limit_price

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
