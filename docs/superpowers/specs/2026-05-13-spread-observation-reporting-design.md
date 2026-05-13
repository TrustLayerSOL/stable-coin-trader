# Spread Observation Reporting Design

## Goal

Add a paper-only measurement layer that records whether real public exchange
snapshots show any repeatable cross-venue stablecoin spread after estimated
fees, slippage, available top-of-book size, and snapshot timing constraints.

## Scope

Included:

- Build spread observations from existing `MarketSnapshot` objects.
- Record both profitable and unprofitable directional routes so the project can
  measure whether an edge exists instead of only logging wins.
- Persist observations as append-only JSON Lines for repeated sampling.
- Summarize observation history from the JSON Lines file.
- Add CLI commands to observe a snapshot file and report stored history.

Excluded:

- Live trading.
- Private exchange credentials.
- Account balances, order placement, fills, or execution routing.
- Scheduling or long-running daemon behavior.
- Research/news scoring.

## Design

Create `src/stable_coin_trader/spread_observations.py` with a
`SpreadObservation` model and pure functions for:

- building directional observations from snapshots grouped by symbol;
- applying estimated fee and slippage basis points;
- skipping routes whose buy/sell snapshots are too far apart in time;
- appending observations to JSON Lines;
- loading JSON Lines history; and
- summarizing count, profitable count, average edge, best route, and observed
  time range.

Observation math mirrors the paper opportunity engine but does not filter out
negative net profit. For each symbol and ordered venue pair, the candidate buy
price is the buy venue ask and the candidate sell price is the sell venue bid.
Executable size is capped by requested size, buy ask size, and sell bid size.
Net profit is gross spread profit minus fee and slippage estimates on both legs.
Net edge basis points use buy notional as the denominator.

Add CLI commands:

```bash
stable-coin-trader observe-spreads \
  --market-data runtime/public_snapshots.json \
  --output runtime/spread_observations.jsonl \
  --size 1000 \
  --fee-bps 0 \
  --slippage-bps 0.5

stable-coin-trader report-spreads \
  --input runtime/spread_observations.jsonl
```

The fetch command remains separate. This keeps the first measurement layer easy
to test and lets repeated sampling be handled by shell, cron, or a later
dedicated scheduler.

## Safety Rules

- Never place orders from observation commands.
- Never read private exchange credentials.
- Treat profitable observations as evidence to investigate, not permission to
  trade.
- Skip stale cross-venue comparisons by default when snapshots are more than
  five seconds apart.
- Store runtime output only under ignored paths such as `runtime/`.

## Success Criteria

- Tests cover spread math, negative observations, stale snapshot skipping,
  JSON Lines persistence, summary reporting, and CLI behavior.
- A real public Kraken/Coinbase snapshot file can be observed and reported.
- Project docs/log clearly state that this is measurement only and live trading
  remains disabled.
