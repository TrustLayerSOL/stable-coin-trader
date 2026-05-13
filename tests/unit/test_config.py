import json
from datetime import datetime, timezone
from decimal import Decimal
from os import PathLike
from pathlib import Path

import pytest
from pydantic import ValidationError

from stable_coin_trader.config import BotConfig, load_config


class CurrentDirectoryPathLike(PathLike[str]):
    def __fspath__(self) -> str:
        return "."


def valid_config_data(tmp_path) -> dict[str, object]:
    return {
        "mode": "paper",
        "ledger_path": str(tmp_path / "paper.sqlite3"),
        "market_data_path": "data/fixtures/market_snapshots.json",
        "research_signals_path": "data/fixtures/research_signals.json",
        "base_currency": "USD",
        "symbols": [" USDC/USD "],
        "venues": [" coinbase ", "\tkraken\n"],
        "max_order_usd": "1000",
        "max_position_usd": "5000",
        "min_edge_bps": "2.5",
        "stale_after_seconds": 20,
        "depeg_threshold_bps": "30",
        "daily_loss_limit_usd": "25",
    }


def test_load_config_from_json(tmp_path) -> None:
    path = tmp_path / "paper.json"
    path.write_text(json.dumps(valid_config_data(tmp_path)))

    config = load_config(path)

    assert config.mode == "paper"
    assert config.ledger_path == tmp_path / "paper.sqlite3"
    assert isinstance(config.ledger_path, Path)
    assert config.market_data_path == Path("data/fixtures/market_snapshots.json")
    assert isinstance(config.market_data_path, Path)
    assert config.research_signals_path == Path("data/fixtures/research_signals.json")
    assert isinstance(config.research_signals_path, Path)
    assert config.symbols == ["USDC/USD"]
    assert config.venues == ["coinbase", "kraken"]
    assert config.max_order_usd == Decimal("1000")
    assert config.min_edge_bps == Decimal("2.5")
    assert config.fee_bps == Decimal("1")
    assert config.slippage_bps == Decimal("0.5")
    assert config.run_as_of is None


def test_load_shipped_paper_example_config() -> None:
    config_path = Path(__file__).resolve().parents[2] / "config" / "paper.example.json"

    config = load_config(config_path)

    assert config.mode == "paper"
    assert config.run_as_of == datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc)


def test_config_rejects_unknown_keys(tmp_path) -> None:
    data = valid_config_data(tmp_path) | {"unexpected": "value"}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


def test_config_rejects_boolean_stale_after_seconds(tmp_path) -> None:
    data = valid_config_data(tmp_path) | {"stale_after_seconds": True}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stale_after_seconds", "20"),
        ("stale_after_seconds", 20.0),
    ],
)
def test_config_rejects_non_integer_stale_after_seconds(tmp_path, field, value) -> None:
    data = valid_config_data(tmp_path) | {field: value}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


def test_config_rejects_empty_symbols(tmp_path) -> None:
    data = valid_config_data(tmp_path) | {"symbols": []}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbols", [" "]),
        ("symbols", ["USDC/USD", "\t"]),
        ("venues", [" "]),
        ("venues", ["coinbase", "\n"]),
    ],
)
def test_config_rejects_blank_symbols_and_venues(tmp_path, field, value) -> None:
    data = valid_config_data(tmp_path) | {field: value}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ledger_path", ""),
        ("ledger_path", " "),
        ("ledger_path", "\t\n"),
        ("ledger_path", "."),
        ("ledger_path", "./"),
        ("ledger_path", "runtime/.."),
        ("ledger_path", "./runtime/.."),
        ("ledger_path", Path(".")),
        ("ledger_path", Path(" ")),
        ("ledger_path", Path("\t\n")),
        ("ledger_path", CurrentDirectoryPathLike()),
        ("market_data_path", ""),
        ("market_data_path", " "),
        ("market_data_path", "\t\n"),
        ("market_data_path", "."),
        ("market_data_path", "./"),
        ("market_data_path", "runtime/.."),
        ("market_data_path", "./runtime/.."),
        ("market_data_path", Path(".")),
        ("market_data_path", Path(" ")),
        ("market_data_path", Path("\t\n")),
        ("market_data_path", CurrentDirectoryPathLike()),
        ("research_signals_path", ""),
        ("research_signals_path", " "),
        ("research_signals_path", "\t\n"),
        ("research_signals_path", "."),
        ("research_signals_path", "./"),
        ("research_signals_path", "runtime/.."),
        ("research_signals_path", "./runtime/.."),
        ("research_signals_path", Path(".")),
        ("research_signals_path", Path(" ")),
        ("research_signals_path", Path("\t\n")),
        ("research_signals_path", CurrentDirectoryPathLike()),
    ],
)
def test_config_rejects_invalid_paths(tmp_path, field, value) -> None:
    data = valid_config_data(tmp_path) | {field: value}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


@pytest.mark.parametrize(
    ("first_field", "second_field"),
    [
        ("ledger_path", "market_data_path"),
        ("ledger_path", "research_signals_path"),
        ("market_data_path", "research_signals_path"),
    ],
)
def test_config_rejects_exact_duplicate_paths(tmp_path, first_field, second_field) -> None:
    duplicate_path = "runtime/shared-path.json"
    data = valid_config_data(tmp_path) | {
        first_field: duplicate_path,
        second_field: duplicate_path,
    }

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


def test_config_rejects_normalized_duplicate_paths(tmp_path) -> None:
    data = valid_config_data(tmp_path) | {
        "ledger_path": "runtime/paper.sqlite3",
        "market_data_path": "runtime/../runtime/paper.sqlite3",
    }

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_order_usd", "0"),
        ("max_order_usd", "-1"),
        ("max_position_usd", "0"),
        ("max_position_usd", "-1"),
        ("depeg_threshold_bps", "0"),
        ("depeg_threshold_bps", "-1"),
        ("daily_loss_limit_usd", "0"),
        ("daily_loss_limit_usd", "-1"),
        ("min_edge_bps", "-1"),
        ("fee_bps", "-1"),
        ("slippage_bps", "-1"),
    ],
)
def test_config_rejects_invalid_money_limits(tmp_path, field, value) -> None:
    data = valid_config_data(tmp_path) | {field: value}

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


def test_config_rejects_max_order_above_max_position(tmp_path) -> None:
    data = valid_config_data(tmp_path) | {
        "max_order_usd": "5001",
        "max_position_usd": "5000",
    }

    with pytest.raises(ValidationError):
        BotConfig.model_validate(data)


def test_load_config_rejects_malformed_top_level_json_shape(tmp_path) -> None:
    path = tmp_path / "paper.json"
    path.write_text("[]")

    with pytest.raises(ValidationError):
        load_config(path)


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
