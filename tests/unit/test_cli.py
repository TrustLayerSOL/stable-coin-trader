import json
from datetime import datetime, timezone
from decimal import Decimal

from typer.testing import CliRunner

from stable_coin_trader.cli import app
from stable_coin_trader.models import MarketSnapshot


def test_cli_without_args_shows_help() -> None:
    result = CliRunner().invoke(app)

    assert result.exit_code == 0
    assert "Risk-aware stablecoin paper trading bot." in result.output


def test_cli_fetch_kraken_snapshots_writes_market_snapshot_json(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeKrakenClient:
        def fetch_order_book_snapshot(self, mapping):
            calls.append((mapping.kraken_pair, mapping.symbol))
            return MarketSnapshot(
                venue="kraken",
                symbol=mapping.symbol,
                bid=Decimal("0.9999"),
                ask=Decimal("1.0001"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("1000"),
                observed_at=datetime(2026, 5, 13, 13, 0, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(
        "stable_coin_trader.cli.KrakenPublicMarketDataClient",
        FakeKrakenClient,
    )
    output = tmp_path / "snapshots.json"

    result = CliRunner().invoke(
        app,
        [
            "fetch-kraken-snapshots",
            "--pair",
            "USDCUSD:USDC/USD",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert calls == [("USDCUSD", "USDC/USD")]
    assert "kraken snapshots written" in result.output
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {
            "venue": "kraken",
            "symbol": "USDC/USD",
            "bid": "0.9999",
            "ask": "1.0001",
            "bid_size": "2000",
            "ask_size": "1000",
            "observed_at": "2026-05-13T13:00:00Z",
        }
    ]


def test_cli_fetch_kraken_snapshots_reports_invalid_pair() -> None:
    result = CliRunner().invoke(
        app,
        [
            "fetch-kraken-snapshots",
            "--pair",
            "USDCUSD",
            "--output",
            "unused.json",
        ],
    )

    assert result.exit_code == 1
    assert "pair mapping" in result.output


def test_cli_fetch_kraken_snapshots_reports_fetch_failure(
    monkeypatch,
    tmp_path,
) -> None:
    class FailingKrakenClient:
        def fetch_order_book_snapshot(self, mapping):
            raise ConnectionError("network down")

    monkeypatch.setattr(
        "stable_coin_trader.cli.KrakenPublicMarketDataClient",
        FailingKrakenClient,
    )

    result = CliRunner().invoke(
        app,
        [
            "fetch-kraken-snapshots",
            "--pair",
            "USDCUSD:USDC/USD",
            "--output",
            str(tmp_path / "unused.json"),
        ],
    )

    assert result.exit_code == 1
    assert "network down" in result.output


def test_cli_fetch_public_snapshots_writes_kraken_and_coinbase_json(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeKrakenClient:
        def fetch_order_book_snapshot(self, mapping):
            calls.append(("kraken", mapping.kraken_pair, mapping.symbol))
            return MarketSnapshot(
                venue="kraken",
                symbol=mapping.symbol,
                bid=Decimal("0.9997"),
                ask=Decimal("0.9998"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("1000"),
                observed_at=datetime(2026, 5, 13, 13, 0, tzinfo=timezone.utc),
            )

    class FakeCoinbaseClient:
        def fetch_order_book_snapshot(self, mapping):
            calls.append(("coinbase", mapping.product_id, mapping.symbol))
            return MarketSnapshot(
                venue="coinbase",
                symbol=mapping.symbol,
                bid=Decimal("0.9999"),
                ask=Decimal("1.0000"),
                bid_size=Decimal("3000"),
                ask_size=Decimal("1500"),
                observed_at=datetime(2026, 5, 13, 13, 0, 1, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(
        "stable_coin_trader.cli.KrakenPublicMarketDataClient",
        FakeKrakenClient,
    )
    monkeypatch.setattr(
        "stable_coin_trader.cli.CoinbasePublicMarketDataClient",
        FakeCoinbaseClient,
    )
    output = tmp_path / "public_snapshots.json"

    result = CliRunner().invoke(
        app,
        [
            "fetch-public-snapshots",
            "--kraken-pair",
            "USDCEUR:USDC/EUR",
            "--coinbase-product",
            "USDC-EUR:USDC/EUR",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("kraken", "USDCEUR", "USDC/EUR"),
        ("coinbase", "USDC-EUR", "USDC/EUR"),
    ]
    assert "public snapshots written" in result.output
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {
            "venue": "kraken",
            "symbol": "USDC/EUR",
            "bid": "0.9997",
            "ask": "0.9998",
            "bid_size": "2000",
            "ask_size": "1000",
            "observed_at": "2026-05-13T13:00:00Z",
        },
        {
            "venue": "coinbase",
            "symbol": "USDC/EUR",
            "bid": "0.9999",
            "ask": "1.0000",
            "bid_size": "3000",
            "ask_size": "1500",
            "observed_at": "2026-05-13T13:00:01Z",
        },
    ]
