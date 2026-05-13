# Stable Coin Trader Project

## Purpose

Build a proprietary stablecoin trading bot for the owner's own capital. The initial product direction is a risk-aware stablecoin trader: USDC-first, spot-only, paper-trading first, with market research and news signals used as a defensive risk layer.

The bot should make money from execution-driven opportunities such as stablecoin spreads, venue fee differences, liquidity differences, and inventory placement. The research engine should help avoid bad trades during issuer, venue, regulatory, macro, or depeg stress.

## Current Status

Current phase: core skeleton implemented and deterministic paper loop runnable.

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

Still not started:

- No API keys or secrets have been added.
- No live trading has been enabled.
- No exchange accounts have been connected.
- No real exchange market-data adapters have been added.

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
|       +-- specs/
|           +-- 2026-05-13-risk-aware-stablecoin-trader-design.md
+-- src/
|   +-- stable_coin_trader/
|       +-- cli.py
|       +-- config.py
|       +-- engine.py
|       +-- ledger.py
|       +-- market_data.py
|       +-- models.py
|       +-- opportunities.py
|       +-- paper.py
|       +-- research.py
|       +-- risk.py
+-- tests/
|   +-- unit/
|   +-- integration/
```

## Design Rules

- Touch only files inside this project folder.
- Never put secrets in git.
- Start with paper trading.
- Live trading must begin with tiny order sizes.
- The research engine cannot originate trades.
- Positive news cannot increase risk beyond the configured baseline.
- Negative or high-risk signals can reduce size, increase required edge, pause trading, or require human review.
- The risk engine is the final authority for every proposed trade.
- Every decision needs a reproducible audit trail.

## Next Steps

1. Complete final verification of the deterministic paper loop.
2. Push the implementation branch to GitHub.
3. Add the first real exchange market-data adapter, likely Kraken or Coinbase.
4. Keep execution in paper mode while validating spreads, stale-data handling, fees, and ledger behavior.
5. Add exchange status and research-source ingestion.
6. Run paper trading before any live trading.
