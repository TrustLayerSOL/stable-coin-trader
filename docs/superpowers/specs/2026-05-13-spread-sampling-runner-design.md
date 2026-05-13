# Spread Sampling Runner Design

## Goal

Add a finite sampling command that repeatedly fetches public Kraken/Coinbase
stablecoin snapshots, converts them into spread observations, and appends those
observations to JSON Lines history so the project can measure whether any
repeatable net edge exists over time.

## Scope

Included:

- Public Kraken and Coinbase snapshot fetching through existing adapters.
- A bounded `sample-spreads` command with `--samples` and `--interval-seconds`.
- Reuse of the spread observation math and JSON Lines persistence layer.
- Failure counting for samples where public data fetch or parsing fails.
- Summary output with sample counts, failure counts, observation counts,
  profitable counts, best route, average edge, and observed time range.

Excluded:

- Live trading.
- Private exchange credentials.
- Account balances, order placement, fills, or execution routing.
- Background daemon behavior.
- Cron setup or long-running automation.
- Research/news scoring.

## Design

Create `src/stable_coin_trader/spread_sampling.py` with:

- `SpreadSampleFailure` for sample number and reason.
- `SpreadSamplingResult` for requested/successful/failed samples, written
  observation count, failures, and a `SpreadObservationSummary`.
- `sample_spreads(...)`, a testable orchestration function that accepts parsed
  Kraken/Coinbase mappings, public clients, Decimal cost assumptions, finite
  sample count, interval seconds, and an injectable sleeper.

Each sample:

1. Fetches all configured Kraken snapshots.
2. Fetches all configured Coinbase snapshots.
3. Builds spread observations with the existing observation math.
4. Appends observations to the configured JSON Lines file.
5. Records failures without placing trades.
6. Sleeps between samples only, never after the final sample.

If a sample fails, the runner records that failure and continues to the next
sample. A failed sample writes no partial observations because partial
cross-venue data can produce misleading routes.

Add CLI command:

```bash
stable-coin-trader sample-spreads \
  --kraken-pair USDCEUR:USDC/EUR \
  --coinbase-product USDC-EUR:USDC/EUR \
  --output runtime/spread_observations.jsonl \
  --samples 120 \
  --interval-seconds 30 \
  --size 1000 \
  --fee-bps 0 \
  --slippage-bps 0.5
```

## Safety Rules

- Never place orders from sampling commands.
- Never read private exchange credentials.
- Treat profitable samples as evidence to investigate, not permission to trade.
- Require at least one public market-data mapping.
- Keep output under ignored runtime paths for local measurement.

## Success Criteria

- Tests cover successful multi-sample runs, failure counting, sleep behavior,
  validation, and CLI output.
- A short real public smoke run can sample Kraken/Coinbase once with
  `--samples 1 --interval-seconds 0`.
- Project docs/log clearly state that sampling is measurement only and live
  trading remains disabled.
