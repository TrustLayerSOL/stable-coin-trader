# Stable Coin Trader Project

## Purpose

Build a proprietary stablecoin trading bot for the owner's own capital. The initial product direction is a risk-aware stablecoin trader: USDC-first, spot-only, paper-trading first, with market research and news signals used as a defensive risk layer.

The bot should make money from execution-driven opportunities such as stablecoin spreads, venue fee differences, liquidity differences, and inventory placement. The research engine should help avoid bad trades during issuer, venue, regulatory, macro, or depeg stress.

## Current Status

Current phase: Task 10 / one-cycle paper engine hardening on branch
`implementation/core-skeleton-paper-loop`.

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

1. Push the implementation branch to GitHub.
2. Add the first real exchange market-data adapter, likely Kraken or Coinbase.
3. Keep execution in paper mode while validating spreads, stale-data handling, fees, and ledger behavior.
4. Add exchange status and research-source ingestion.
5. Run paper trading before any live trading.
