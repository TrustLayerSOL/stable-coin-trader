# Coinbase Public Market Data Design

## Goal

Add a second public exchange market-data adapter so the paper trader can compare real Kraken and Coinbase top-of-book prices without private credentials or live execution.

## Scope

Included:

- Coinbase Exchange public REST market data only.
- Level 1 product book from `/products/{product_id}/book?level=1`.
- Conversion into the existing `MarketSnapshot` JSON format with venue `coinbase`.
- A combined CLI command that can fetch Kraken and Coinbase snapshots into one JSON file.

Excluded:

- Coinbase private authentication.
- Balances, orders, fills, account state, or live execution.
- Websocket streaming.
- Scheduling.

## Design

Create `src/stable_coin_trader/coinbase.py` with a small public client. It accepts mappings such as `USDC-EUR:USDC/EUR`, fetches Coinbase Exchange level-1 book data, validates bids and asks, and returns `MarketSnapshot` objects. `MarketSnapshot.observed_at` is the bot fetch time.

Move JSON snapshot writing into `src/stable_coin_trader/market_data.py` so Kraken, Coinbase, and future adapters share one output format.

Add a combined CLI command:

```bash
stable-coin-trader fetch-public-snapshots \
  --kraken-pair USDCEUR:USDC/EUR \
  --coinbase-product USDC-EUR:USDC/EUR \
  --output runtime/public_snapshots.json
```

Users can point a paper config's `market_data_path` at that output file. For real fetched data, the config should remove the fixed fixture `run_as_of` or set it to the fetch time.

## Safety Rules

- Never commit real API keys.
- Do not read private Coinbase or Kraken credentials.
- Public fetch failures produce a command error and never trigger trades.
- The trading engine remains paper-only.

## References

- Coinbase Exchange product book docs: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductbook
- Coinbase Exchange products docs: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs
