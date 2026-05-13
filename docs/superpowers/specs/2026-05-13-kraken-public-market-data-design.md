# Kraken Public Market Data Design

## Goal

Add the first real exchange market-data path without enabling live trading or storing secrets. The adapter fetches Kraken public order-book data and converts it into the existing `MarketSnapshot` JSON format that the paper engine already consumes.

## Scope

Included:

- Public Kraken REST market data only.
- Level 2 order-book top-of-book snapshots from `/0/public/Depth`.
- No API key, private key, balances, orders, or account endpoints.
- CLI command that writes snapshots to a JSON file.
- `.env.example` placeholders for future private credentials only.

Excluded:

- Live execution.
- Private Kraken authentication.
- Balance reads.
- Order placement or cancellation.
- Automatic scheduling.

## Design

Create `src/stable_coin_trader/kraken.py` with a small public client. The client accepts Kraken pair mappings such as `USDCUSD:USDC/USD`, fetches one public order book per mapping, validates Kraken's JSON response, and returns `MarketSnapshot` objects with venue `kraken`.

`MarketSnapshot.observed_at` is the bot fetch time, not the Kraken book-level timestamp. The engine uses this field for stale-data filtering and opportunity identity, so it must represent when this bot observed the book.

The CLI gets a new command:

```bash
stable-coin-trader fetch-kraken-snapshots \
  --pair USDCUSD:USDC/USD \
  --output runtime/kraken_snapshots.json
```

The output file is a JSON list shaped like the existing fixture file. Users can point `market_data_path` at that file and run the existing paper engine unchanged.
When using real fetched data, the fixed fixture `run_as_of` should be removed or set to the fetch time so stale-data checks use the correct clock.

## Safety Rules

- Never commit real Kraken API keys.
- Do not read private credentials for this feature.
- Network failures and Kraken API errors fail the fetch command; they do not trigger trades.
- The trading engine remains paper-only.

## References

- Kraken REST market data docs: https://docs.kraken.com/api/docs/category/rest-api/market-data/
- Kraken public order book endpoint: https://docs.kraken.com/api/docs/rest-api/get-order-book/
- Kraken public endpoint examples: https://support.kraken.com/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser-
