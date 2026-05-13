import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from stable_coin_trader.config import BotConfig, load_config


def test_load_config_from_json(tmp_path) -> None:
    path = tmp_path / "paper.json"
    path.write_text(
        json.dumps(
            {
                "mode": "paper",
                "ledger_path": str(tmp_path / "paper.sqlite3"),
                "market_data_path": "data/fixtures/market_snapshots.json",
                "research_signals_path": "data/fixtures/research_signals.json",
                "base_currency": "USD",
                "symbols": ["USDC/USD"],
                "venues": ["coinbase", "kraken"],
                "max_order_usd": "1000",
                "max_position_usd": "5000",
                "min_edge_bps": "2.5",
                "stale_after_seconds": 20,
                "depeg_threshold_bps": "30",
                "daily_loss_limit_usd": "25",
            }
        )
    )

    config = load_config(path)

    assert config.mode == "paper"
    assert config.max_order_usd == Decimal("1000")
    assert config.min_edge_bps == Decimal("2.5")


def test_config_rejects_live_mode() -> None:
    with pytest.raises(ValidationError):
        BotConfig(
            mode="live",
            ledger_path="paper.sqlite3",
            market_data_path="data/fixtures/market_snapshots.json",
            research_signals_path="data/fixtures/research_signals.json",
            base_currency="USD",
            symbols=["USDC/USD"],
            venues=["coinbase"],
            max_order_usd="1000",
            max_position_usd="5000",
            min_edge_bps="2.5",
            stale_after_seconds=20,
            depeg_threshold_bps="30",
            daily_loss_limit_usd="25",
        )


def test_config_rejects_empty_venues() -> None:
    with pytest.raises(ValidationError):
        BotConfig(
            mode="paper",
            ledger_path="paper.sqlite3",
            market_data_path="data/fixtures/market_snapshots.json",
            research_signals_path="data/fixtures/research_signals.json",
            base_currency="USD",
            symbols=["USDC/USD"],
            venues=[],
            max_order_usd="1000",
            max_position_usd="5000",
            min_edge_bps="2.5",
            stale_after_seconds=20,
            depeg_threshold_bps="30",
            daily_loss_limit_usd="25",
        )
