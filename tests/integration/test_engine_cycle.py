import json
from decimal import Decimal
from pathlib import Path

from stable_coin_trader.config import BotConfig
from stable_coin_trader.engine import run_once
from stable_coin_trader.ledger import Ledger


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _profitable_market() -> list[dict[str, str]]:
    return [
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


def _flat_market() -> list[dict[str, str]]:
    return [
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
            "bid": "0.9998",
            "ask": "1.0001",
            "bid_size": "25000",
            "ask_size": "25000",
            "observed_at": "2026-05-13T12:00:00Z",
        },
    ]


def _human_review_signal() -> list[dict[str, object]]:
    return [
        {
            "id": "sig-review",
            "observed_at": "2026-05-13T12:00:00Z",
            "published_at": "2026-05-13T11:59:00Z",
            "source": "fixture",
            "source_url": "https://example.com/signal",
            "source_quality": 1.0,
            "affected_assets": ["USDC"],
            "affected_venues": [],
            "event_type": "issuer_reserve",
            "direction": "neutral",
            "severity": 3,
            "confidence": 0.8,
            "ttl_seconds": 315360000,
            "summary": "Reserve report needs manual review.",
            "human_review_required": True,
        }
    ]


def _config(
    tmp_path,
    market_data: list[dict[str, object]],
    research_signals: list[dict[str, object]],
) -> BotConfig:
    market_path = tmp_path / "market.json"
    signals_path = tmp_path / "signals.json"
    _write_json(market_path, market_data)
    _write_json(signals_path, research_signals)

    return BotConfig(
        mode="paper",
        ledger_path=tmp_path / "paper.sqlite3",
        market_data_path=market_path,
        research_signals_path=signals_path,
        base_currency="USD",
        symbols=["USDC/USD"],
        venues=["coinbase", "kraken"],
        max_order_usd="1000",
        max_position_usd="5000",
        min_edge_bps="1",
        stale_after_seconds=20,
        depeg_threshold_bps="30",
        daily_loss_limit_usd="25",
    )


def _ledger(config: BotConfig) -> Ledger:
    return Ledger(config.ledger_path)


def test_run_once_records_decision_and_fill(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    result = run_once(config)

    ledger = _ledger(config)
    assert result.opportunities_seen == 1
    assert result.approved_trades == 2
    assert result.rejected_trades == 0
    assert result.paper_fills == 2
    assert len(ledger.fetch_all("select * from risk_decisions")) == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 2


def test_run_once_records_rejected_decisions_when_research_requires_review(
    tmp_path,
) -> None:
    config = _config(tmp_path, _profitable_market(), _human_review_signal())

    result = run_once(config)

    decisions = _ledger(config).fetch_all("select * from risk_decisions order by id")
    assert result.opportunities_seen == 1
    assert result.approved_trades == 0
    assert result.rejected_trades == 2
    assert result.paper_fills == 0
    assert [row["approved"] for row in decisions] == [0, 0]
    assert [row["requires_human_approval"] for row in decisions] == [1, 1]
    assert {row["reason"] for row in decisions} == {
        "human review required by research signal"
    }
    assert [json.loads(row["active_signal_ids"]) for row in decisions] == [
        ["sig-review"],
        ["sig-review"],
    ]
    assert _ledger(config).fetch_all("select * from paper_fills") == []


def test_run_once_with_no_opportunities_initializes_empty_ledger(tmp_path) -> None:
    config = _config(tmp_path, _flat_market(), [])

    result = run_once(config)

    ledger = _ledger(config)
    assert result.opportunities_seen == 0
    assert result.approved_trades == 0
    assert result.rejected_trades == 0
    assert result.paper_fills == 0
    assert ledger.fetch_all("select * from risk_decisions") == []
    assert ledger.fetch_all("select * from paper_fills") == []


def test_run_once_links_each_fill_to_matching_approved_decision(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    result = run_once(config)

    ledger = _ledger(config)
    decisions = ledger.fetch_all("select * from risk_decisions order by id")
    fills = ledger.fetch_all("select * from paper_fills order by id")
    decisions_by_id = {row["id"]: row for row in decisions}

    assert result.approved_trades == 2
    assert result.paper_fills == 2
    assert {fill["risk_decision_id"] for fill in fills} == set(decisions_by_id)

    for fill in fills:
        decision = decisions_by_id[fill["risk_decision_id"]]
        assert decision["approved"] == 1
        assert fill["opportunity_id"] == decision["opportunity_id"]
        assert fill["venue"] == decision["venue"]
        assert fill["symbol"] == decision["symbol"]
        assert fill["side"] == decision["side"]
        assert Decimal(fill["size"]) == Decimal(decision["size"])
        assert Decimal(fill["price"]) == Decimal(decision["limit_price"])
        assert Decimal(fill["fee"]) == (
            Decimal(fill["size"]) * Decimal(fill["price"]) * Decimal("1")
        ) / Decimal("10000")
