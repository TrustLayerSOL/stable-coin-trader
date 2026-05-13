# Risk-Aware Stablecoin Trader Design

Date: 2026-05-13

## Status

Approved direction: start with Approach 2, the Risk-Aware Stablecoin Trader, then expand toward Approach 3 only after the core trading loop is proven.

This document is a design spec. It is not legal, tax, or financial advice. The bot is intended for proprietary use with the owner's own capital only.

## Goal

Build a professional stablecoin trading bot that can identify and execute stablecoin opportunities while controlling issuer, venue, depeg, liquidity, operational, tax, and research-signal risk.

The first version should prove that the system can:

- Find realistic stablecoin spread opportunities.
- Model fees, slippage, latency, and partial fills.
- Paper trade with reliable accounting.
- Apply risk constraints before every trade.
- Use market research and news to reduce risk, pause activity, or require review.
- Produce an auditable ledger and decision history.

## Non-Goals

The first version will not:

- Trade customer funds.
- Pool capital.
- Offer copy trading or signals to others.
- Use unsupported offshore exchanges.
- Use VPN or false-location access.
- Use leverage or offshore perpetual futures.
- Use news or LLM sentiment to create orders directly.
- Implement flash-loan or sandwich-style MEV.
- Start with fully autonomous depeg speculation.

## Strategy Selection

Three approaches were considered.

Approach 1: Simple Arbitrage Bot

- Lowest complexity.
- CEX-only spread scanner and executor.
- Weakness: too narrow and likely to lose edge quickly after real fees and slippage.

Approach 2: Risk-Aware Stablecoin Trader

- CEX-first stablecoin spread trading with paper mode, risk controls, ledger, and research context.
- Research signals influence risk constraints, not trade direction.
- Best chance of success because it proves the core loop while avoiding hidden operational risk.

Approach 3: Full Intelligence Platform

- CEX, DEX, yield routing, on-chain intelligence, social signals, macro feeds, and dashboard from day one.
- Powerful long term, but too much surface area before the trading core is proven.

Decision: build Approach 2 first, then graduate toward Approach 3 after evidence from paper and small live trading.

## Trading Scope

Initial asset focus:

- USDC/USD
- USDC/USDT
- USDC/PYUSD
- USDC/RLUSD
- USD/USDC settlement behavior where supported

Initial venue focus:

- U.S.-available, KYC exchanges with official APIs.
- Candidate venues include Coinbase, Kraken, Gemini, and Binance.US where available and permitted.

Initial execution style:

- Paper trading first.
- Live trading only after paper-mode evidence.
- Tiny live orders first.
- Spot-only.
- Limit-order preference.
- No leverage.
- No unsupported derivatives.

## Success Metrics

The MVP is successful when it can show:

- Accurate detected opportunity count.
- Accurate net-edge calculation after fees and slippage.
- Paper fills and missed fills that match market conditions reasonably.
- Reconciled balances and ledger state.
- Clear reason for every accepted or rejected trade.
- Stable operation through restarts.
- No trade without a recorded risk decision.
- Research signals that reduce risk during credible stress events without excessive false pauses.

Key metrics:

- Gross spread detected.
- Net spread after fees and slippage.
- Fill ratio.
- Partial-fill rate.
- Missed-trade rate.
- Realized PnL in paper mode.
- False positive pause rate.
- False negative risk-event rate.
- Maximum drawdown in paper and small live mode.
- Ledger reconciliation errors.
- Exchange API error rate.

## System Architecture

The system should be layered so each part has one clear job.

```text
Market Data Sources       Research Sources
        |                       |
        v                       v
Market Data Layer        Research Ingestion
        |                       |
        v                       v
Opportunity Engine       Research Signal Engine
        |                       |
        +-----------> Risk Engine <----------+
                         |
                         v
                 Trade Decision Engine
                         |
                         v
                  Execution Engine
                         |
                         v
                  Ledger and Monitoring
```

### Configuration

Responsibilities:

- Load environment-specific settings.
- Validate required keys and safety settings.
- Keep secrets out of git.
- Define venues, assets, limits, strategies, and paper/live mode.

Configuration should fail closed if required safety settings are missing.

### Exchange Adapters

Responsibilities:

- Provide normalized market data.
- Provide balances.
- Place, cancel, and query orders.
- Track fills and partial fills.
- Respect rate limits.
- Surface venue-specific quirks.

Initial CEX implementation should use official exchange APIs directly or CCXT where it is reliable. Exchange-specific behavior must be isolated behind adapter tests.

### Market Data Layer

Responsibilities:

- Ingest order books, tickers, trades, and fee schedules.
- Track staleness.
- Normalize symbols.
- Calculate executable prices for configured order sizes.
- Provide market snapshots to the opportunity engine.

### Opportunity Engine

Responsibilities:

- Find stablecoin spread opportunities.
- Model total cost:
  - Maker/taker fees.
  - Slippage.
  - Spread.
  - Minimum order sizes.
  - Partial-fill risk.
  - Transfer cost if relevant.
  - Gas cost for later DEX routes.
- Emit proposed trades, not final decisions.

The opportunity engine does not know whether a trade is allowed. It only reports whether an opportunity appears profitable under market assumptions.

### Research Engine

Responsibilities:

- Ingest news, status, macro, issuer, stablecoin, and on-chain sources.
- Normalize raw inputs into structured risk signals.
- Store provenance for every signal.
- Emit risk annotations to the risk engine.

The research engine cannot originate trades. It cannot approve trades. It cannot increase risk beyond configured baseline limits.

Initial low-cost source stack:

- GDELT for broad global news.
- CryptoPanic for crypto-native headlines.
- CoinGecko for trending categories and market context.
- DeFiLlama for stablecoin supply, yield, and chain distribution.
- FRED, U.S. Treasury, and Federal Reserve RSS for macro/rate context.
- Exchange status pages and status APIs.
- Alchemy or Etherscan for basic on-chain monitoring.

Later paid or advanced sources:

- Trading Economics for structured macro calendar and live releases.
- LunarCrush or X API for social trend intelligence.
- Whale Alert for large transfer alerts.
- Nansen, Glassnode, or similar for labeled on-chain flow intelligence.

### Research Signal Schema

Research signals should be structured, not free-form sentiment.

```json
{
  "id": "signal-uuid",
  "observed_at": "2026-05-13T00:00:00Z",
  "published_at": "2026-05-13T00:00:00Z",
  "source": "coinbase_status",
  "source_url": "https://status.coinbase.com/",
  "source_quality": 0.95,
  "affected_assets": ["USDC"],
  "affected_venues": ["coinbase"],
  "event_type": "outage",
  "direction": "risk_increase",
  "severity": 4,
  "confidence": 0.9,
  "corroboration_count": 1,
  "actionability": 0.8,
  "ttl_seconds": 3600,
  "human_review_required": true,
  "summary": "Coinbase reports delayed sends or receives for an affected network."
}
```

Signal event types:

- `depeg_risk`
- `issuer_reserve`
- `issuer_redemption`
- `venue_outage`
- `withdrawal_delay`
- `regulatory`
- `macro`
- `liquidity`
- `oracle`
- `rumor`
- `social_trend`
- `informational`

### Risk Engine

Responsibilities:

- Be the final authority for trade approval.
- Convert baseline config, market conditions, and research signals into constraints.
- Approve, reject, reduce, or require human review for proposed trades.
- Record the exact reason for every decision.

Research can tighten risk, but cannot loosen risk beyond baseline.

Examples of constraints:

```json
{
  "asset": "USDC",
  "venue": "coinbase",
  "max_position_usd": 25000,
  "max_order_usd": 5000,
  "min_edge_bps": 18,
  "allow_new_exposure": false,
  "allow_reduce_only": true,
  "requires_human_approval": true,
  "expires_at": "2026-05-13T22:00:00Z"
}
```

Hard blocks:

- Exchange trading halted.
- Exchange API degraded beyond threshold.
- Withdrawals disabled or materially delayed for an affected asset.
- Stablecoin price moves outside configured peg threshold.
- Issuer confirms reserve or redemption impairment.
- Ledger reconciliation fails.
- Missing or stale market data.

Soft-risk clusters can also reduce or pause trading if deterministic thresholds are met. For example, USDC trades materially below peg, a major venue has withdrawal delays, and multiple credible sources report issuer or banking stress. This should trigger reduce-only or pause even before an official statement.

### Trade Decision Engine

Responsibilities:

- Combine opportunity proposals with risk decisions.
- Ensure idempotency.
- Prevent duplicate orders.
- Produce a clear decision record.

The trade decision engine cannot bypass the risk engine.

### Execution Engine

Responsibilities:

- Execute approved paper or live orders.
- Prefer limit orders for controlled execution.
- Track order lifecycle.
- Handle partial fills.
- Cancel stale orders.
- Reconcile expected versus actual fills.
- Stop after repeated execution errors.

Live mode should begin with tiny order sizes and strict per-trade and daily loss caps.

### Ledger

Responsibilities:

- Store all orders, fills, fees, transfers, balances, and research-influenced decisions.
- Track cost basis and lots.
- Separate trading PnL from transfers.
- Support daily reconciliation.
- Export tax/accounting-friendly records.

The system must maintain its own canonical ledger and not rely only on exchange statements or tax forms.

### Monitoring

Responsibilities:

- Show bot mode: paper, live, paused, reduce-only.
- Show active constraints.
- Show current positions and exposure by asset, issuer, and venue.
- Show opportunity feed and rejected-trade reasons.
- Show exchange API health.
- Show research signal feed.
- Alert on depeg, venue outage, ledger mismatch, and repeated execution failure.

## Data Flow

1. Market data adapters emit normalized snapshots.
2. The opportunity engine calculates candidate trades.
3. Research ingestion normalizes external context into signals.
4. The risk engine computes active constraints.
5. Each candidate trade is submitted to the risk engine.
6. The trade decision engine approves or rejects the trade.
7. The execution engine places paper or live orders.
8. The ledger records decisions, orders, fills, fees, balances, and signals.
9. Monitoring surfaces status, alerts, and audit data.

## Error Handling

The system should fail closed for trading-critical errors.

Examples:

- If market data is stale, reject affected trades.
- If balances cannot be read, reject affected trades.
- If the ledger cannot write, stop trading.
- If risk rules cannot load, stop trading.
- If an exchange API returns repeated errors, pause that venue.
- If research feeds fail, continue baseline trading only if issuer, venue, and depeg hard checks remain healthy.
- If official status sources are unavailable during a stress event, reduce size or require review.

## Research Engine Safety Rules

- The research engine is advisory only.
- LLM output must be extraction and classification only.
- LLM output must be strict JSON and schema validated.
- Source links and timestamps are required.
- Signals must expire.
- Independent corroboration must count original sources, not syndicated copies.
- Prompt/model versions must be stored.
- Prompt injection cannot affect execution because research has no execution authority.
- Positive sentiment can restore normal limits after evidence, but cannot exceed baseline limits.
- Resuming from severe pause requires human review.

## Testing Strategy

Unit tests:

- Symbol normalization.
- Fee calculation.
- Net-edge calculation.
- Risk constraint evaluation.
- Research signal parsing and validation.
- Ledger writes and reads.

Integration tests:

- Mock exchange adapters.
- Mock order books and fills.
- Paper execution lifecycle.
- Partial fills and cancellations.
- Restart and reconciliation.
- Research signal ingestion.

Backtests and replays:

- Normal stablecoin market periods.
- USDC March 2023 depeg.
- UST collapse as a risk-control replay, not a target asset.
- Tether stress periods.
- Exchange withdrawal or API outage periods.
- False rumor and false alarm periods.

Acceptance checks before live mode:

- Paper ledger reconciles.
- Trade decisions are auditable.
- Risk engine blocks known bad scenarios.
- Kill switch works.
- Config prevents live mode without explicit opt-in.
- Secrets are not present in git.

## Implementation Phases

### Phase 0: Documentation and Bootstrap

Current phase.

Deliverables:

- Project guide.
- Project log.
- Design spec.
- Implementation plan.
- Initial repo hygiene.

### Phase 1: Core Skeleton

Deliverables:

- Project package structure.
- Configuration loader.
- Logging.
- SQLite or Postgres-backed ledger.
- Risk policy model.
- Paper execution interface.
- Test harness.

### Phase 2: Market Data and Paper Opportunities

Deliverables:

- Coinbase, Kraken, Gemini, and Binance.US market data adapters where available.
- Fee and slippage model.
- Stablecoin spread opportunity engine.
- Paper-trading loop.
- Reconciliation reports.

### Phase 3: Research and Risk Integration

Deliverables:

- Exchange status ingestion.
- DeFiLlama stablecoin data ingestion.
- CoinGecko market/trending context.
- GDELT and CryptoPanic headline ingestion.
- Structured research signals.
- Risk constraints from signals.
- Signal and decision audit views.

### Phase 4: Tiny Live Trading

Deliverables:

- Live order execution for one venue pair.
- Explicit live-mode opt-in.
- Max order and max daily loss caps.
- Kill switch.
- Daily reconciliation.

### Phase 5: Expansion Toward Approach 3

Deliverables:

- DEX quote and execution adapters.
- Yield routing for idle inventory.
- Richer on-chain flow intelligence.
- Optional social intelligence if proven useful.
- Operator dashboard.

## Open Decisions

These should be decided in the implementation plan:

- Python versus TypeScript for the first implementation.
- SQLite versus Postgres for the initial ledger.
- Direct exchange APIs versus CCXT for each venue.
- Exact first venue and first pair.
- Whether dashboard comes before or after tiny live trading.
- Which paid data sources, if any, are worth adding after paper testing.

## Recommended Defaults

- Language: Python for first version, because the strongest bot, data, and research ecosystem is available there.
- Ledger: SQLite for MVP, designed so Postgres can replace it later.
- Exchange access: start with direct official APIs for the first venue and consider CCXT where it reduces friction without hiding important quirks.
- First strategy: USDC/USD or USDC/stablecoin paper spread trading on one or two U.S.-available venues.
- First research sources: exchange status, DeFiLlama, CoinGecko, GDELT, CryptoPanic, FRED/Treasury/Fed RSS.

## Approval Gate

After this spec is reviewed, the next step is to write an implementation plan. No trading code should be written until the implementation plan is approved.
