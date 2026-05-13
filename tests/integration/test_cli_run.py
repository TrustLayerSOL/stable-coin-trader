import json

from typer.testing import CliRunner

from stable_coin_trader.cli import app


def test_cli_run_once(tmp_path) -> None:
    market_path = tmp_path / "market.json"
    market_path.write_text(
        json.dumps(
            [
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "1.0000",
                    "ask": "1.0002",
                    "bid_size": "50000",
                    "ask_size": "50000",
                    "observed_at": "2026-05-13T12:00:00Z",
                },
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9994",
                    "ask": "0.9996",
                    "bid_size": "25000",
                    "ask_size": "25000",
                    "observed_at": "2026-05-13T12:00:00Z",
                },
            ]
        ),
        encoding="utf-8",
    )
    signals_path = tmp_path / "signals.json"
    signals_path.write_text("[]", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "mode": "paper",
                "ledger_path": str(tmp_path / "paper.sqlite3"),
                "market_data_path": str(market_path),
                "research_signals_path": str(signals_path),
                "base_currency": "USD",
                "symbols": ["USDC/USD"],
                "venues": ["coinbase", "kraken"],
                "max_order_usd": "1000",
                "max_position_usd": "5000",
                "min_edge_bps": "1",
                "stale_after_seconds": 315360000,
                "depeg_threshold_bps": "30",
                "daily_loss_limit_usd": "25",
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["run-once", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "opportunities=1" in result.output
    assert "approved=2" in result.output
    assert "rejected=0" in result.output
    assert "fills=2" in result.output
