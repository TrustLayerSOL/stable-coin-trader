# Stable Coin Trader Project

## Purpose

Build a professional-grade proprietary stablecoin trading bot for the owner's own capital. The objective is to find, validate, and operate repeatable trading edges that can produce consistent risk-adjusted profits after fees, slippage, stale-data controls, and operational constraints.

The bot should make money from execution-driven opportunities such as stablecoin spreads, venue fee differences, liquidity differences, and inventory placement. The research engine should help avoid bad trades during issuer, venue, regulatory, macro, or depeg stress. Profitability must be demonstrated through paper trading, audit logs, and small controlled live experiments before any meaningful capital is deployed.

## Current Status

Current phase: public Kraken/Coinbase spread measurement on `main`.
The initial PR stack has been merged through the spread sampling runner.

The near-term architecture remains phase 2 first: deterministic stablecoin
spread paper trading, followed later by the phase 3 research/news layer after
the core loop is proven.

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

Still not started:

- No live trading has been enabled.
- No exchange accounts have been connected.
- No private exchange API calls have been added.

## Selected Approach

Start with Approach 2, then expand toward Approach 3 after proof.

Approach 2 means:

- CEX-first stablecoin spread detection and paper execution.
- USDC-first, U.S.-available, KYC exchange support.
- Risk engine as the authority for all trade approvals.
- Research/news/trend engine as a risk and context layer only.
- Full ledger and audit trail from day one.

Approach 3 comes later:

- DEX execution.
- Yield routing for idle inventory.
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
+-- src/
|   +-- stable_coin_trader/
|       +-- cli.py
|       +-- coinbase.py
|       +-- config.py
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
- Every decision needs a reproducible audit trail.

## Next Steps

1. Run longer public Kraken/Coinbase spread observations before any live trading.
2. Add an edge analysis report that summarizes route-level hit rate, best/worst edge, average edge, failure rate, and cost sensitivity.
3. Feed measured observations into paper trading with realistic fees, slippage, and stale-data controls.
4. Add exchange status and research-source ingestion after measurement is running.
5. Add storage rotation or a database-backed observation store if JSON Lines history grows beyond practical file size.
6. Only consider tiny live execution after observations and paper trading show a repeatable net edge after costs.
