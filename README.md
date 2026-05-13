# Stable Coin Trader

Professional-grade, risk-aware stablecoin trading bot for proprietary capital.

Current phase: public Kraken/Coinbase market data plus paper-only spread observation reporting. The project does not contain live trading code yet.

The project goal is to find and validate repeatable stablecoin trading edges that can generate consistent risk-adjusted profits after fees, slippage, stale-data controls, and operational constraints. Profitability is not assumed; it must be proven through paper trading, logs, and small controlled live experiments before capital is scaled.

Safety rules:

- No secrets in git.
- Paper mode first.
- Consistent profit is the goal, not an assumption.
- Risk engine approves every proposed trade.
- Research signals can reduce risk, pause trading, or require review, but cannot originate trades.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -v
```

## Run One Paper Cycle

```bash
stable-coin-trader run-once --config config/paper.example.json
```

Expected output includes:

```text
paper run complete opportunities=1 approved=2 rejected=0 fills=2
```

The example config writes to `runtime/paper.sqlite3`, which is ignored by git.
It uses a fixed `run_as_of` timestamp so the fixture replay and audit timestamps are deterministic.
If you run it again against the same local ledger, already-filled opportunities
are skipped and the output will show zero new fills.

## Fetch Public Market Data

Kraken and Coinbase public order-book data do not require API credentials.

Fetch a two-venue snapshot file:

```bash
stable-coin-trader fetch-public-snapshots \
  --kraken-pair USDCEUR:USDC/EUR \
  --coinbase-product USDC-EUR:USDC/EUR \
  --output runtime/public_snapshots.json
```

Fetch Kraken only:

```bash
stable-coin-trader fetch-kraken-snapshots \
  --pair USDCUSD:USDC/USD \
  --output runtime/kraken_snapshots.json
```

Then point a paper config's `market_data_path` at the generated JSON file.
For real fetched data, remove the fixed fixture `run_as_of` value or set it to
the fetch time so the engine's stale-data checks use the right clock.
These fetch commands never place orders and do not read private exchange keys.

## Observe Spreads

Record spread observations from a snapshot file:

```bash
stable-coin-trader observe-spreads \
  --market-data runtime/public_snapshots.json \
  --output runtime/spread_observations.jsonl \
  --size 1000 \
  --fee-bps 0 \
  --slippage-bps 0.5
```

Summarize the observation history:

```bash
stable-coin-trader report-spreads \
  --input runtime/spread_observations.jsonl
```

Observation commands do not create trades. They record both profitable and
unprofitable directional routes so the project can measure whether an edge
exists over time.

## Current Layout

```text
config/paper.example.json                 Paper-mode demo config
data/fixtures/market_snapshots.json       Deterministic market snapshot fixture
data/fixtures/research_signals.json       Defensive research-signal fixture
data/fixtures/research_signals_empty.json Demo fixture with no active research signals
src/stable_coin_trader/config.py          Safe paper config loader
src/stable_coin_trader/coinbase.py        Coinbase public market-data adapter
src/stable_coin_trader/ledger.py          SQLite risk-decision and paper-fill ledger
src/stable_coin_trader/kraken.py          Kraken public market-data adapter
src/stable_coin_trader/market_data.py     Fixture market-data loader
src/stable_coin_trader/research.py        Fixture research-signal loader
src/stable_coin_trader/opportunities.py   Stablecoin spread opportunity engine
src/stable_coin_trader/spread_observations.py Spread measurement and reporting
src/stable_coin_trader/risk.py            Risk decision engine
src/stable_coin_trader/paper.py           Paper executor
src/stable_coin_trader/engine.py          One-cycle orchestration
src/stable_coin_trader/cli.py             CLI entry point
tests/                                    Unit and integration coverage
```
