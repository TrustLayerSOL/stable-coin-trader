# Adaptive Liquidity Intelligence Engine Design

## Goal

Build a professional-grade Adaptive Liquidity Intelligence Engine for proprietary capital. The system should find, validate, and eventually execute repeatable liquidity edges across CEX, DEX, derivatives, market-making, momentum, and inventory-management strategies.

Profitability is not assumed. Every edge must be measured, paper traded, audited, and proven after fees, slippage, stale-data controls, funding costs, gas costs, inventory constraints, venue risk, and operational risk before capital is scaled.

## Product Shape

The system is one unified liquidity platform, not separate bots. Strategy modules can propose actions, but shared pricing, inventory, risk, execution, and ledger layers must govern all activity.

Initial implementation remains paper-only. Live execution, private account access, DEX transactions, derivatives, and market-making quotes are out of scope until the measurement and simulation layers demonstrate reliable behavior.

## Layers

### Market Data Layer

Collects raw market and context data:

- CEX order books and trades.
- DEX pool states and route quotes.
- Funding rates, futures, perpetuals, and basis data.
- Gas costs, chain status, bridge status, and venue status.
- Account balances and positions when private APIs are later enabled.
- Research, news, regulatory, issuer, depeg, and macro risk signals.

### Normalization Layer

Converts all venue-specific data into common internal models:

- Asset identifiers.
- Venue identifiers.
- Pairs and routes.
- Order books and pool quotes.
- Fee schedules.
- Timestamps and freshness.
- Liquidity depth.
- Reliability and confidence metadata.

### Pricing Engine

Computes the system's shared view of executable value:

- Fair value.
- Executable bid/ask.
- Spread.
- Slippage.
- Top-of-book and depth-aware capacity.
- Fee-adjusted edge.
- Gas-adjusted DEX edge.
- Funding-adjusted carry.
- Stale-data penalty.
- Confidence score.

The pricing engine should be the next core module after the current observer dashboard work, because every strategy needs one consistent cost and edge calculation.

### Strategy Module Layer

Strategy modules produce proposals, not final orders:

- Cross-exchange arbitrage.
- Triangular arbitrage.
- DEX/CEX arbitrage.
- Funding-rate and basis arbitrage.
- Market making.
- Momentum.
- Inventory hedging.
- Depeg/repeg behavior later.

Each proposal should include expected edge, size, route, required inventory, expected holding time, dependencies, confidence, and failure modes.

### Inventory And Hedging Layer

Tracks capital state and portfolio constraints:

- Balances by asset and venue.
- Target inventory.
- Maximum inventory drift.
- Open exposure.
- Hedge requirements.
- Collateral and margin use.
- Funding and borrow exposure.
- Idle capital.
- Capital that should not be deployed.

Inventory hedging is a core portfolio function, not an isolated bot. It should reduce unwanted exposure created by arbitrage, market making, momentum, or funding strategies.

### Risk Engine

The risk engine is the final authority for every proposed action. It can approve, reject, resize, pause, or require human review.

The risk engine must consider:

- Maximum capital exposure.
- Per-venue exposure.
- Per-asset exposure.
- Inventory drift.
- Stale data.
- Liquidity depth.
- Slippage and fees.
- DEX gas and execution risk.
- Funding-rate and liquidation risk.
- Venue outage or degraded status.
- Issuer, depeg, regulatory, and macro risk.
- Research and news risk.
- Kill switches.

No strategy may bypass the risk engine.

### Execution And Routing Layer

Routes approved actions to paper execution first, and later to live venues after separate approval.

Execution should support:

- Paper fills.
- Route simulation.
- Atomic multi-leg paper fills where needed.
- Order preflight checks.
- Tiny live controlled tests later.
- Clear separation between public market data, private account reads, and order placement.

### Ledger And Analytics Layer

Records the full decision trail:

- Raw observations.
- Normalized market state.
- Pricing calculations.
- Strategy proposals.
- Risk decisions.
- Rejections.
- Paper fills.
- Live fills later.
- PnL.
- Missed opportunities.
- Post-trade outcomes.

The ledger must make every decision reproducible.

### GUI And Operations Layer

Shows the operator:

- Market data health.
- Pricing engine output.
- Strategy proposals.
- Risk approvals and rejections.
- Inventory and hedge state.
- Paper/live PnL.
- Venue status.
- Logs and alerts.
- Kill-switch state.

The current temporary observer dashboard is an early read-only tool, not the final GUI.

## First Implementation Sequence

1. Finish or merge the temporary observer dashboard branch.
2. Add an edge analysis report for the completed observation history.
3. Build the first pricing engine slice for CEX spot spreads.
4. Add a strategy module interface.
5. Convert the current CEX spread detector into the first arbitrage strategy module.
6. Add paper inventory state and basic inventory hedging models.
7. Expand market data coverage across more CEX pairs and venues.
8. Add funding-rate, DEX/CEX, market-making, and momentum modules as paper-only modules.
9. Consider tiny live tests only after measured paper results show repeatable net edge after all costs and controls.

## Non-Goals For The Next Slice

- No live trading.
- No private exchange credentials.
- No private account reads.
- No DEX transactions.
- No derivatives positions.
- No automated market-making quotes.
- No strategy that can bypass risk review.

## Success Criteria

The next implementation slice is successful when:

- Edge analysis can explain whether observed spreads were tradable after costs.
- Pricing calculations are centralized instead of duplicated across strategy logic.
- Strategy proposals use a shared interface.
- Current CEX spread behavior still works in paper mode.
- Risk remains the final approval layer.
- Tests cover the new pricing and strategy boundaries.
