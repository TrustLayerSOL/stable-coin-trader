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
