# Project Log

## 2026-05-13

### Research

- Investigated stablecoin money-making strategies:
  - CEX/CEX and CEX/DEX stablecoin arbitrage.
  - Stablecoin market making.
  - Idle inventory yield routing.
  - DEX concentrated liquidity.
  - Depeg/repeg monitoring.
  - Funding and basis trades where legally available.
- Investigated GitHub references:
  - `ccxt/ccxt`
  - `freqtrade/freqtrade`
  - `hummingbot/hummingbot`
  - `hummingbot/gateway`
  - `BowTiedDevil/degenbot`
  - `curvefi/curve-js`
  - `jordantete/grid_trading_bot`
- Investigated U.S. constraints:
  - Own-capital proprietary trading is the intended use.
  - Avoid customer funds, copy trading, pooled capital, and unsupported offshore venues.
  - Keep full tax and audit records.

### Product Direction

- Chose Approach 2: Risk-Aware Stablecoin Trader.
- Agreed to prove Approach 2 before expanding toward Approach 3.
- Decided the research engine should make the bot more cautious, not more aggressive.
- Clarified the project north star: build a professional-grade bot that can find and validate repeatable stablecoin trading edges capable of consistent risk-adjusted profits after all costs and controls.
- Consistent profit is treated as a target to prove with data, not an assumption.

### Repository Setup

- Confirmed the local folder was empty.
- Connected the folder to `trustlayersol/stable-coin-trader`.
- The remote appeared to be an empty repository.

### Documentation

- Created `PROJECT.md`.
- Created this project log.
- Created the initial design spec at `docs/superpowers/specs/2026-05-13-risk-aware-stablecoin-trader-design.md`.

### Current State

- Design documentation has been approved.
- The first implementation plan has been executed through the deterministic paper loop.
- The codebase now has a runnable paper-only CLI and test-covered core modules.
- No live trading is enabled.

### Implementation Planning

- Created the first implementation plan at `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.
- Plan scope: Python bootstrap, config, models, SQLite ledger, fixture market data, fixture research signals, opportunity engine, risk engine, paper executor, one-cycle engine, and CLI.
- Deferred live trading, exchange API adapters, DEX execution, dashboard, and paid research sources to later plans.

### Core Skeleton Implementation

- Bootstrapped the Python package and CLI.
- Added paper-only config validation with explicit fee, slippage, stale-data, risk-limit, and path checks.
- Added domain models for market snapshots, opportunities, proposed trades, research signals, and risk decisions.
- Added a SQLite ledger with risk-decision and paper-fill audit records.
- Added deterministic fixture loaders for market data and research signals.
- Added a cross-venue stablecoin opportunity engine with fee, slippage, depth, and sorting behavior.
- Added a risk engine that gates every proposed trade and treats research signals as defensive constraints only.
- Added a paper executor that records risk decisions before fills and links fills to approved decisions.
- Added one-cycle orchestration and the `stable-coin-trader run-once` CLI command.
- Added integration coverage for the full fixture-based paper loop.

### Current Implementation State

- Paper loop works with `config/paper.example.json`.
- Example CLI output: `paper run complete opportunities=1 approved=2 rejected=0 fills=2`.
- Live trading, real exchange APIs, DEX execution, dashboarding, and paid research sources remain deferred.

### Task 10 Hardening Pass

- Current branch: `implementation/core-skeleton-paper-loop`.
- Current task: Task 10 / one-cycle paper engine hardening.
- Architecture remains phase 2 first: deterministic stablecoin spread paper trading, with phase 3 research/news expansion deferred until the core loop is proven.
- Hardening completed for fail-closed ledger exposure reads, engine-clock checks for future-dated and stale market data, engine-clock research signal loading, future-dated research signal filtering, configurable fee and slippage basis points, deterministic fixture replay via `run_as_of`, duplicate already-filled opportunity skipping, observation-scoped opportunity IDs, and atomic pair execution.
- Atomic pair execution records approved paper legs in one ledger transaction so both legs are recorded together or no fills are recorded.
- Duplicate opportunity fills are guarded inside the ledger write transaction so overlapping runs cannot both fill the same opportunity.
- Verification completed: full automated test suite passed with 275 tests.
- The example CLI run against the existing local `runtime/paper.sqlite3` ledger returned zero new fills, confirming duplicate-fill protection on repeated runs.

### Kraken Public Market Data Adapter

- Started branch `feature/kraken-public-market-data` from the hardened core skeleton.
- Added a design spec at `docs/superpowers/specs/2026-05-13-kraken-public-market-data-design.md`.
- Added an implementation plan at `docs/superpowers/plans/2026-05-13-kraken-public-market-data.md`.
- Scope is public Kraken market data only: no private keys, balances, orders, or live execution.
- Added `.env.example` placeholders for future Kraken private credentials, but the current adapter does not read them.
- Added `stable-coin-trader fetch-kraken-snapshots` to write public order-book snapshots in the existing fixture JSON shape.

### Coinbase Public Market Data Adapter

- Started branch `feature/coinbase-public-market-data` from the Kraken public market-data branch.
- Added a design spec at `docs/superpowers/specs/2026-05-13-coinbase-public-market-data-design.md`.
- Added an implementation plan at `docs/superpowers/plans/2026-05-13-coinbase-public-market-data.md`.
- Scope is public Coinbase Exchange market data only: no private keys, balances, orders, or live execution.
- Added a Coinbase public REST client for level-1 product book snapshots.
- Added `stable-coin-trader fetch-public-snapshots` to write Kraken and Coinbase snapshots into one JSON file for two-venue paper spread checks.
- Verified the branch with 304 passing tests, a clean whitespace check, a committed-file secret scan, and a live public Kraken/Coinbase snapshot smoke test.
- Opened draft PR #3: `https://github.com/TrustLayerSOL/stable-coin-trader/pull/3`.

### Spread Observation Reporting

- Started branch `feature/spread-observation-reporting` from the Coinbase public market-data branch.
- Added a design spec at `docs/superpowers/specs/2026-05-13-spread-observation-reporting-design.md`.
- Added an implementation plan at `docs/superpowers/plans/2026-05-13-spread-observation-reporting.md`.
- Scope is paper-only measurement: no credentials, private endpoints, orders, balances, fills, or live execution.
- Added spread observations that record profitable and unprofitable directional routes after estimated fees, slippage, top-of-book depth, and snapshot lag checks.
- Added append-only JSON Lines observation history and summary reporting.
- Added `stable-coin-trader observe-spreads` and `stable-coin-trader report-spreads`.
- Verification completed: full automated test suite passed with 324 tests, whitespace check passed, committed-file secret scan passed, and a live public Kraken/Coinbase snapshot -> observe -> report smoke test completed.
- The live smoke report recorded 2 observations and 0 profitable routes after configured slippage, demonstrating that the measurement layer can produce a no-trade signal.
- Opened draft PR #4: `https://github.com/TrustLayerSOL/stable-coin-trader/pull/4`.
