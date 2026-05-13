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


def test_cli_observe_spreads_appends_jsonl_and_prints_summary(tmp_path) -> None:
    market_data = tmp_path / "public_snapshots.json"
    output = tmp_path / "spread_observations.jsonl"
    market_data.write_text(
        json.dumps(
            [
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9994",
                    "ask": "0.9996",
                    "bid_size": "2000",
                    "ask_size": "2000",
                    "observed_at": "2026-05-13T13:00:00Z",
                },
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "1.0000",
                    "ask": "1.0002",
                    "bid_size": "2000",
                    "ask_size": "2000",
                    "observed_at": "2026-05-13T13:00:01Z",
                },
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "observe-spreads",
            "--market-data",
            str(market_data),
            "--output",
            str(output),
            "--size",
            "1000",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
            "--max-snapshot-lag-seconds",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "spread observations recorded" in result.output
    assert "count=2" in result.output
    assert "profitable=1" in result.output
    assert "best=kraken->coinbase USDC/USD" in result.output
    assert "first=2026-05-13T13:00:01Z" in result.output
    assert "last=2026-05-13T13:00:01Z" in result.output

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["buy_venue"] == "kraken"


def test_cli_report_spreads_summarizes_jsonl_history(tmp_path) -> None:
    market_data = tmp_path / "public_snapshots.json"
    observations = tmp_path / "spread_observations.jsonl"
    market_data.write_text(
        json.dumps(
            [
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9994",
                    "ask": "0.9996",
                    "bid_size": "2000",
                    "ask_size": "2000",
                    "observed_at": "2026-05-13T13:00:00Z",
                },
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "1.0000",
                    "ask": "1.0002",
                    "bid_size": "2000",
                    "ask_size": "2000",
                    "observed_at": "2026-05-13T13:00:01Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    create_result = CliRunner().invoke(
        app,
        [
            "observe-spreads",
            "--market-data",
            str(market_data),
            "--output",
            str(observations),
            "--size",
            "1000",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
        ],
    )
    assert create_result.exit_code == 0

    result = CliRunner().invoke(
        app,
        [
            "report-spreads",
            "--input",
            str(observations),
        ],
    )

    assert result.exit_code == 0
    assert "spread observation report" in result.output
    assert "count=2" in result.output
    assert "profitable=1" in result.output
    assert "best=kraken->coinbase USDC/USD" in result.output
    assert "first=2026-05-13T13:00:01Z" in result.output
    assert "last=2026-05-13T13:00:01Z" in result.output


def test_cli_sample_spreads_fetches_repeated_public_snapshots(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeKrakenClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_order_book_snapshot(self, mapping):
            self.calls += 1
            calls.append(("kraken", mapping.kraken_pair, mapping.symbol))
            return MarketSnapshot(
                venue="kraken",
                symbol=mapping.symbol,
                bid=Decimal("0.9994"),
                ask=Decimal("0.9996"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("2000"),
                observed_at=datetime(
                    2026,
                    5,
                    13,
                    14,
                    0,
                    self.calls,
                    tzinfo=timezone.utc,
                ),
            )

    class FakeCoinbaseClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_order_book_snapshot(self, mapping):
            self.calls += 1
            calls.append(("coinbase", mapping.product_id, mapping.symbol))
            return MarketSnapshot(
                venue="coinbase",
                symbol=mapping.symbol,
                bid=Decimal("1.0000"),
                ask=Decimal("1.0002"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("2000"),
                observed_at=datetime(
                    2026,
                    5,
                    13,
                    14,
                    0,
                    self.calls,
                    tzinfo=timezone.utc,
                ),
            )

    monkeypatch.setattr(
        "stable_coin_trader.cli.KrakenPublicMarketDataClient",
        FakeKrakenClient,
    )
    monkeypatch.setattr(
        "stable_coin_trader.cli.CoinbasePublicMarketDataClient",
        FakeCoinbaseClient,
    )
    output = tmp_path / "sampled_spreads.jsonl"

    result = CliRunner().invoke(
        app,
        [
            "sample-spreads",
            "--kraken-pair",
            "USDCUSD:USDC/USD",
            "--coinbase-product",
            "USDC-USD:USDC/USD",
            "--output",
            str(output),
            "--samples",
            "2",
            "--interval-seconds",
            "0",
            "--size",
            "1000",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("kraken", "USDCUSD", "USDC/USD"),
        ("coinbase", "USDC-USD", "USDC/USD"),
        ("kraken", "USDCUSD", "USDC/USD"),
        ("coinbase", "USDC-USD", "USDC/USD"),
    ]
    assert "spread sampling complete" in result.output
    assert "samples=2" in result.output
    assert "successful=2" in result.output
    assert "failed=0" in result.output
    assert "count=4" in result.output
    assert "profitable=2" in result.output
    assert len(output.read_text(encoding="utf-8").splitlines()) == 4


def test_cli_sample_spreads_reports_sample_failure_reason(
    monkeypatch,
    tmp_path,
) -> None:
    class FakeKrakenClient:
        def fetch_order_book_snapshot(self, mapping):
            return MarketSnapshot(
                venue="kraken",
                symbol=mapping.symbol,
                bid=Decimal("0.9994"),
                ask=Decimal("0.9996"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("2000"),
                observed_at=datetime(2026, 5, 13, 14, 0, tzinfo=timezone.utc),
            )

    class FailingOnceCoinbaseClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_order_book_snapshot(self, mapping):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("temporary public API failure")
            return MarketSnapshot(
                venue="coinbase",
                symbol=mapping.symbol,
                bid=Decimal("1.0000"),
                ask=Decimal("1.0002"),
                bid_size=Decimal("2000"),
                ask_size=Decimal("2000"),
                observed_at=datetime(2026, 5, 13, 14, 0, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(
        "stable_coin_trader.cli.KrakenPublicMarketDataClient",
        FakeKrakenClient,
    )
    monkeypatch.setattr(
        "stable_coin_trader.cli.CoinbasePublicMarketDataClient",
        FailingOnceCoinbaseClient,
    )
    output = tmp_path / "sampled_spreads.jsonl"

    result = CliRunner().invoke(
        app,
        [
            "sample-spreads",
            "--kraken-pair",
            "USDCUSD:USDC/USD",
            "--coinbase-product",
            "USDC-USD:USDC/USD",
            "--output",
            str(output),
            "--samples",
            "2",
            "--interval-seconds",
            "0",
            "--size",
            "1000",
            "--fee-bps",
            "0",
            "--slippage-bps",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "sample=1 status=failed observations=0" in result.output
    assert "temporary public API failure" in result.output
    assert "sample=2 status=successful observations=2" in result.output
    assert "successful=1" in result.output
    assert "failed=1" in result.output
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_cli_sample_spreads_reports_output_write_failure(
    monkeypatch,
    tmp_path,
) -> None:
    def fail_sample_spreads(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "stable_coin_trader.cli.sample_spreads",
        fail_sample_spreads,
    )

    result = CliRunner().invoke(
        app,
        [
            "sample-spreads",
            "--kraken-pair",
            "USDCUSD:USDC/USD",
            "--coinbase-product",
            "USDC-USD:USDC/USD",
            "--output",
            str(tmp_path / "sampled_spreads.jsonl"),
            "--samples",
            "1",
            "--interval-seconds",
            "0",
        ],
    )

    assert result.exit_code == 1
    assert "spread sampling failed: disk full" in result.output
