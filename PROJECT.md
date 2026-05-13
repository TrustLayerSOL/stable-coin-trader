# Stable Coin Trader Project

## Purpose

Build a proprietary stablecoin trading bot for the owner's own capital. The initial product direction is a risk-aware stablecoin trader: USDC-first, spot-only, paper-trading first, with market research and news signals used as a defensive risk layer.

The bot should make money from execution-driven opportunities such as stablecoin spreads, venue fee differences, liquidity differences, and inventory placement. The research engine should help avoid bad trades during issuer, venue, regulatory, macro, or depeg stress.

## Current Status

Current phase: implementation plan written and pending execution choice.

Completed:

- Researched stablecoin profit strategies.
- Researched relevant GitHub projects and frameworks.
- Confirmed the bot will trade only the owner's own capital.
- Selected Approach 2: Risk-Aware Stablecoin Trader.
- Connected this local folder to `trustlayersol/stable-coin-trader`.
- Created the initial design spec.
- Created the first implementation plan: `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.

Not started:

- No trading code has been implemented.
- No API keys or secrets have been added.
- No live trading has been enabled.
- No exchange accounts have been connected.

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

## Proposed Project Layout

The implementation plan may refine this, but the expected layout is:

```text
.
+-- PROJECT.md
+-- PROJECT_LOG.md
+-- docs/
|   +-- superpowers/
|       +-- specs/
|           +-- 2026-05-13-risk-aware-stablecoin-trader-design.md
+-- src/
|   +-- stable_coin_trader/
|       +-- config/
|       +-- exchanges/
|       +-- market_data/
|       +-- research/
|       +-- opportunities/
|       +-- risk/
|       +-- execution/
|       +-- ledger/
|       +-- monitoring/
+-- tests/
|   +-- unit/
|   +-- integration/
|   +-- fixtures/
+-- scripts/
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

1. Review the first implementation plan in `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.
2. Choose Subagent-Driven or Inline Execution for that plan.
3. Build the project skeleton, config system, ledger schema, and paper-trading loop.
4. Add exchange market-data adapters.
5. Add the opportunity engine and risk engine.
6. Add research signal ingestion.
7. Run paper trading before any live trading.
