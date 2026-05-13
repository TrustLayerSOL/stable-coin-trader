# Stable Coin Trader Project

Target product: an Adaptive Liquidity Intelligence Engine.

## Purpose

Build a professional-grade proprietary liquidity intelligence and trading system for the owner's own capital. The objective is to find, validate, and operate repeatable trading edges that can produce consistent risk-adjusted profits after fees, slippage, stale-data controls, inventory constraints, funding costs, venue risk, and operational constraints.

The system should not be a pile of separate bots. It should be one adaptive liquidity engine with shared market data, pricing, strategy, inventory, hedging, risk, execution, and analytics layers. Strategy modules can propose trades, but the unified risk engine and inventory layer decide whether anything can happen.

The engine should make money from execution-driven opportunities such as stablecoin spreads, venue fee differences, liquidity differences, funding-rate and basis dislocations, DEX/CEX dislocations, market-making spreads, momentum signals, and inventory placement. The research engine should help avoid bad trades during issuer, venue, regulatory, macro, funding, or depeg stress. Profitability must be demonstrated through paper trading, audit logs, and small controlled live experiments before any meaningful capital is deployed.

## Current Status

Current phase: public Kraken/Coinbase spread measurement plus a temporary observer dashboard.
The initial PR stack has been merged through the spread sampling runner.

The near-term architecture is still measurement first. The current code proves
the basic public-data, paper-only loop before adding live execution, private
account access, DEX execution, derivatives, or market making.

Completed:

- Researched stablecoin profit strategies.
- Researched relevant GitHub projects and frameworks.
- Confirmed the bot will trade only the owner's own capital.
- Selected Approach 2: Risk-Aware Stablecoin Trader.
- Connected this local folder to `trustlayersol/stable-coin-trader`.
- Created the initial design spec.
- Created the first implementation plan: `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.
- Implemented the Python package, safe config loader, domain models, SQLite ledger, fixture loaders, opportunity engine, risk engine, paper executor, one-cycle engine, and CLI.
- Added deterministic fixture data and integration tests for the paper loop.
- Opened draft PR #1 for the core skeleton paper loop.
- Opened draft PR #2 for the Kraken public market-data adapter.
- Opened draft PR #3 for the Coinbase public market-data adapter.
- Started the spread observation reporting layer.
- Opened draft PR #4 for spread observation reporting.
- Started the spread sampling runner.
- Opened draft PR #5 for the spread sampling runner.
- Merged PRs #1-#5 into `main`.
- Ran the first merged-main public spread sampling pass: 20 samples, 40 observations, 0 profitable routes after 0.5 bps slippage.
- Completed a 2-hour public USDC/EUR sampling canary and added a temporary read-only local dashboard on port `8777`.
- Reframed the long-term product as an Adaptive Liquidity Intelligence Engine with market data, pricing, strategy, inventory, hedging, risk, execution, ledger, analytics, and GUI layers.

Task 10 hardening completed:

- Fail closed when existing ledger exposure cannot be read.
- Reject future-dated and stale market data using the engine clock.
- Load research signals using the engine clock.
- Support configurable fee and slippage basis points.
- Use `run_as_of` in the example config to replay fixtures deterministically.
- Skip duplicate already-filled opportunities on repeated runs.
- Allow the same prices to trade again at a new market observation time.
- Ignore future-dated research signals.
- Add atomic pair execution so both paper legs are recorded together or no fills are recorded.
- Guard duplicate opportunity fills inside the ledger write transaction for overlapping runs.
- Verified with the full automated test suite.

Kraken public market-data adapter completed:

- Fetches public Kraken order-book snapshots from `/0/public/Depth`.
- Converts top-of-book data into the existing `MarketSnapshot` JSON format.
- Adds a CLI command to write snapshots to `runtime/kraken_snapshots.json` or another selected path.
- Does not use Kraken private API keys, balances, orders, or account endpoints.

Coinbase public market-data adapter completed:

- Fetches public Coinbase Exchange level-1 product book snapshots from `/products/{product_id}/book`.
- Converts top-of-book data into the existing `MarketSnapshot` JSON format.
- Adds a combined CLI command that writes Kraken and Coinbase snapshots into one JSON file.
- Does not use Coinbase private API keys, balances, orders, or account endpoints.

Spread observation reporting completed:

- Builds directional spread observations from public snapshot files.
- Records profitable and unprofitable routes so the project can measure edge quality over time.
- Stores repeated observations as append-only JSON Lines under ignored runtime paths.
- Adds report summaries for observation count, profitable count, best route, and average edge.
- Does not place orders, read credentials, or enable live trading.

Spread sampling runner implemented on branch:

- Repeatedly fetches public Kraken/Coinbase snapshots for a finite number of samples.
- Appends spread observations to JSON Lines history with a local file lock and atomic replace.
- Counts successful samples, failed samples, observations, profitable routes, and edge summaries.
- Prints per-sample success and failure progress for operator visibility.
- Sleeps only between samples and stops after the requested sample count.
- Does not place orders, read credentials, or enable live trading.

2-hour public USDC/EUR canary completed:

- 240 samples collected.
- 480 directional route observations recorded.
- 0 sampler failures.
- 0 profitable observations after configured cost assumptions.
- Best route: `kraken->coinbase USDC/EUR`.
- Best observed edge: `-1` bps.
- Average edge: `-2.17068085` bps.
- Current conclusion: this USDC/EUR Kraken/Coinbase route does not show a tradable edge under the tested assumptions.

Still not started:

- No live trading has been enabled.
- No exchange accounts have been connected.
- No private exchange API calls have been added.

## Target Architecture

The target system is an Adaptive Liquidity Intelligence Engine with these layers:

1. Market data layer
   - Collects CEX order books, DEX pool states, funding rates, futures/perpetual data, gas costs, venue status, wallet/account state, and research/news signals.
2. Normalization layer
   - Converts venue-specific data into common asset, venue, pair, book, pool, fee, timestamp, and reliability models.
3. Pricing engine
   - Computes fair value, executable price, spread, depth, slippage, fees, gas-adjusted DEX cost, funding-adjusted carry, stale-data penalties, and confidence scores.
4. Strategy module layer
   - Hosts independent modules for cross-exchange arbitrage, triangular arbitrage, DEX/CEX arbitrage, funding-rate and basis arbitrage, market making, momentum, and later depeg/repeg behavior.
5. Inventory and hedging layer
   - Tracks balances, target inventory, venue allocation, open exposure, hedge needs, collateral, funding exposure, and capital that should stay idle.
6. Risk engine
   - Final authority for every proposed action. It can approve, reject, resize, pause, or require human review.
7. Execution and routing layer
   - Eventually routes orders across supported venues, but remains paper-only until evidence justifies tiny controlled live tests.
8. Ledger and analytics layer
   - Records quotes, observations, signals, strategy proposals, risk decisions, simulated fills, live fills, PnL, missed opportunities, and post-trade outcomes.
9. GUI and operations layer
   - Shows market state, strategy performance, inventory, risks, rejected trades, open orders, PnL, logs, and system health.

Strategy modules are not allowed to bypass inventory, risk, execution controls, or the ledger. Market maker, arbitrage engine, momentum engine, funding-rate engine, and inventory hedger should be strategy or portfolio modules inside the unified system, not isolated bots.

## Selected Approach

Start with CEX spot measurement as the first proving ground, then expand into
the full Adaptive Liquidity Intelligence Engine after each layer has evidence,
tests, and paper results.

Approach 2 means:

- CEX-first stablecoin spread detection and paper execution.
- USDC-first, U.S.-available, KYC exchange support.
- Risk engine as the authority for all trade approvals.
- Research/news/trend engine as a risk and context layer only.
- Full ledger and audit trail from day one.
- A pricing engine and strategy interface before adding more strategy families.

Later modules:

- DEX execution.
- DEX/CEX arbitrage.
- Funding-rate and basis arbitrage.
- Market making.
- Momentum signals.
- Inventory hedging.
- Yield routing for idle inventory if risk-adjusted returns justify it.
- Richer on-chain intelligence.
- Social trend intelligence.
- Broader dashboard and operations tooling.

## Project Layout

```text
.
+-- PROJECT.md
+-- PROJECT_LOG.md
+-- README.md
+-- config/
|   +-- paper.example.json
+-- data/
|   +-- fixtures/
|       +-- market_snapshots.json
|       +-- research_signals.json
|       +-- research_signals_empty.json
+-- docs/
|   +-- superpowers/
|       +-- plans/
|       |   +-- 2026-05-13-core-skeleton-paper-loop.md
|       |   +-- 2026-05-13-kraken-public-market-data.md
|       |   +-- 2026-05-13-coinbase-public-market-data.md
|       |   +-- 2026-05-13-spread-observation-reporting.md
|       |   +-- 2026-05-13-spread-sampling-runner.md
|       +-- specs/
|           +-- 2026-05-13-risk-aware-stablecoin-trader-design.md
|           +-- 2026-05-13-kraken-public-market-data-design.md
|           +-- 2026-05-13-coinbase-public-market-data-design.md
|           +-- 2026-05-13-spread-observation-reporting-design.md
|           +-- 2026-05-13-spread-sampling-runner-design.md
|           +-- 2026-05-13-adaptive-liquidity-intelligence-engine-design.md
+-- src/
|   +-- stable_coin_trader/
|       +-- cli.py
|       +-- coinbase.py
|       +-- config.py
|       +-- dashboard.py
|       +-- engine.py
|       +-- kraken.py
|       +-- ledger.py
|       +-- market_data.py
|       +-- models.py
|       +-- opportunities.py
|       +-- paper.py
|       +-- research.py
|       +-- risk.py
|       +-- spread_observations.py
|       +-- spread_sampling.py
+-- tests/
|   +-- unit/
|   +-- integration/
```

## Design Rules

- Touch only files inside this project folder.
- Never put secrets in git.
- Start with paper trading.
- Treat consistent profit as the goal, not an assumption; every edge must be measured and proven after costs.
- Live trading must begin with tiny order sizes.
- The research engine cannot originate trades.
- Positive news cannot increase risk beyond the configured baseline.
- Negative or high-risk signals can reduce size, increase required edge, pause trading, or require human review.
- The risk engine is the final authority for every proposed trade.
- Every strategy module proposes; the risk engine, inventory layer, and execution layer dispose.
- No live execution, DEX transaction, derivative position, or market-making quote can bypass risk checks.
- Every decision needs a reproducible audit trail.

## Next Steps

1. Finish and merge the temporary observer dashboard branch or decide to keep it as a short-lived tool.
2. Add an edge analysis report that summarizes route-level hit rate, best/worst edge, average edge, failure rate, cost sensitivity, and minimum edge required.
3. Build the first pricing engine slice so spreads, fees, slippage, stale-data penalties, and confidence are calculated in one place.
4. Add a strategy module interface and convert the current CEX spread detector into the first arbitrage strategy module.
5. Add paper inventory state and a basic inventory hedger model before any live order placement.
6. Expand sampling across more CEX pairs and venues after the analysis report exists.
7. Add funding-rate, DEX/CEX, market-making, and momentum modules only as measured paper strategies first.
8. Only consider tiny live execution after observations and paper trading show a repeatable net edge after all costs and controls.
