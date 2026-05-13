from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from hashlib import sha256

from stable_coin_trader.models import MarketSnapshot, Opportunity, decimal_key


def bps_cost(notional: Decimal, bps: Decimal) -> Decimal:
    return notional * bps / Decimal("10000")


def _validate_inputs(size: Decimal, fee_bps: Decimal, slippage_bps: Decimal) -> None:
    if not size.is_finite():
        raise ValueError("size must be finite")
    if size <= 0:
        raise ValueError("size must be positive")

    for name, value in (
        ("fee_bps", fee_bps),
        ("slippage_bps", slippage_bps),
    ):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")


def find_spread_opportunities(
    snapshots: list[MarketSnapshot],
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> list[Opportunity]:
    _validate_inputs(size=size, fee_bps=fee_bps, slippage_bps=slippage_bps)

    by_symbol: dict[str, list[MarketSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_symbol[snapshot.symbol].append(snapshot)

    opportunities: list[Opportunity] = []
    for symbol, symbol_snapshots in by_symbol.items():
        for buy in symbol_snapshots:
            for sell in symbol_snapshots:
                if buy.venue == sell.venue:
                    continue

                executable_size = min(size, buy.ask_size, sell.bid_size)
                if executable_size <= 0:
                    continue

                buy_notional = buy.ask * executable_size
                sell_notional = sell.bid * executable_size
                opportunity = Opportunity(
                    id=_stable_opportunity_id(
                        symbol=symbol,
                        buy=buy,
                        sell=sell,
                        size=executable_size,
                    ),
                    buy_venue=buy.venue,
                    sell_venue=sell.venue,
                    symbol=symbol,
                    size=executable_size,
                    buy_price=buy.ask,
                    sell_price=sell.bid,
                    estimated_fees=bps_cost(buy_notional + sell_notional, fee_bps),
                    estimated_slippage=bps_cost(
                        buy_notional + sell_notional,
                        slippage_bps,
                    ),
                    observed_at=max(buy.observed_at, sell.observed_at),
                )
                if opportunity.net_profit > 0:
                    opportunities.append(opportunity)

    return sorted(
        opportunities,
        key=lambda item: (
            -item.net_profit,
            item.symbol,
            item.buy_venue,
            item.sell_venue,
            item.buy_price,
            item.sell_price,
            item.size,
            item.observed_at,
        ),
    )


def _stable_opportunity_id(
    symbol: str,
    buy: MarketSnapshot,
    sell: MarketSnapshot,
    size: Decimal,
) -> str:
    raw = "|".join(
        (
            "spread",
            symbol,
            buy.venue,
            sell.venue,
            decimal_key(size),
            decimal_key(buy.ask),
            decimal_key(sell.bid),
            buy.observed_at.isoformat(),
            sell.observed_at.isoformat(),
        )
    )
    return f"spread-{sha256(raw.encode('utf-8')).hexdigest()[:24]}"
