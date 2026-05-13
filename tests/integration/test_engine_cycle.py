import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest

from stable_coin_trader.config import BotConfig
from stable_coin_trader.engine import run_once
from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import ProposedTrade, RiskDecision


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


def _market_observed_at(observed_at: str) -> list[dict[str, str]]:
    market = _profitable_market()
    for snapshot in market:
        snapshot["observed_at"] = observed_at
    return market


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
    **overrides: object,
) -> BotConfig:
    market_path = tmp_path / "market.json"
    signals_path = tmp_path / "signals.json"
    _write_json(market_path, market_data)
    _write_json(signals_path, research_signals)

    values: dict[str, object] = {
        "mode": "paper",
        "ledger_path": tmp_path / "paper.sqlite3",
        "market_data_path": market_path,
        "research_signals_path": signals_path,
        "base_currency": "USD",
        "symbols": ["USDC/USD"],
        "venues": ["coinbase", "kraken"],
        "max_order_usd": "1000",
        "max_position_usd": "5000",
        "min_edge_bps": "1",
        "stale_after_seconds": 20,
        "depeg_threshold_bps": "30",
        "daily_loss_limit_usd": "25",
    }
    values.update(overrides)
    return BotConfig(**values)


def _ledger(config: BotConfig) -> Ledger:
    return Ledger(config.ledger_path)


def test_run_once_records_decision_and_fill(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])
    now = datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc)

    result = run_once(
        config,
        now=now,
    )

    ledger = _ledger(config)
    decisions = ledger.fetch_all("select * from risk_decisions")
    fills = ledger.fetch_all("select * from paper_fills")
    assert result.opportunities_seen == 1
    assert result.approved_trades == 2
    assert result.rejected_trades == 0
    assert result.paper_fills == 2
    assert len(decisions) == 2
    assert len(fills) == 2
    assert {row["created_at"] for row in decisions} == {now.isoformat()}
    assert {row["created_at"] for row in fills} == {now.isoformat()}


def test_run_once_records_rejected_decisions_when_research_requires_review(
    tmp_path,
) -> None:
    config = _config(tmp_path, _profitable_market(), _human_review_signal())

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

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

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    ledger = _ledger(config)
    assert result.opportunities_seen == 0
    assert result.approved_trades == 0
    assert result.rejected_trades == 0
    assert result.paper_fills == 0
    assert ledger.fetch_all("select * from risk_decisions") == []
    assert ledger.fetch_all("select * from paper_fills") == []


def test_run_once_links_each_fill_to_matching_approved_decision(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

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


def test_run_once_evaluates_pair_before_filling_either_leg(tmp_path) -> None:
    config = _config(
        tmp_path,
        _profitable_market(),
        [],
        max_position_usd="1500",
    )

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    ledger = _ledger(config)
    assert result.approved_trades == 2
    assert result.rejected_trades == 0
    assert result.paper_fills == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 2


def test_run_once_does_not_fill_when_one_leg_would_exceed_existing_exposure(
    tmp_path,
) -> None:
    config = _config(
        tmp_path,
        _profitable_market(),
        [],
        max_position_usd="1500",
    )
    ledger = _ledger(config)
    ledger.initialize()
    decision_id = ledger.record_risk_decision(
        RiskDecision.approve(
            trade=ProposedTrade(
                opportunity_id="existing",
                side="buy",
                venue="kraken",
                symbol="USDC/USD",
                size=Decimal("1000"),
                limit_price=Decimal("0.9995"),
            ),
            reason="existing approved exposure",
            min_edge_bps=Decimal("1"),
        )
    )
    ledger.record_paper_fill(
        risk_decision_id=decision_id,
        opportunity_id="existing",
        venue="kraken",
        symbol="USDC/USD",
        side="buy",
        size=Decimal("1000"),
        price=Decimal("0.9995"),
        fee=Decimal("0"),
    )

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    assert result.approved_trades == 0
    assert result.rejected_trades == 2
    assert result.paper_fills == 0
    assert len(ledger.fetch_all("select * from paper_fills")) == 1


def test_run_once_ignores_stale_market_data(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 1, 0, tzinfo=timezone.utc),
    )

    assert result.opportunities_seen == 0
    assert result.approved_trades == 0
    assert result.rejected_trades == 0
    assert result.paper_fills == 0


def test_run_once_rejects_future_dated_market_data(tmp_path) -> None:
    config = _config(tmp_path, _market_observed_at("2026-05-13T12:00:00Z"), [])

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 11, 59, 59, tzinfo=timezone.utc),
    )

    assert result.opportunities_seen == 0
    assert result.approved_trades == 0
    assert result.paper_fills == 0


def test_run_once_uses_engine_clock_for_research_signal_expiration(tmp_path) -> None:
    config = _config(
        tmp_path,
        _market_observed_at("2099-01-01T00:00:00Z"),
        [
            {
                "id": "expired-review",
                "observed_at": "2099-01-01T00:00:00Z",
                "published_at": "2098-12-31T23:59:00Z",
                "source": "fixture",
                "source_url": "https://example.com/expired-review",
                "source_quality": 1.0,
                "affected_assets": ["USDC"],
                "affected_venues": [],
                "event_type": "issuer_reserve",
                "direction": "neutral",
                "severity": 5,
                "confidence": 1.0,
                "ttl_seconds": 5,
                "summary": "Expired review signal.",
                "human_review_required": True,
            }
        ],
    )

    result = run_once(
        config,
        now=datetime(2099, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
    )

    assert result.opportunities_seen == 1
    assert result.approved_trades == 2
    assert result.rejected_trades == 0
    assert result.paper_fills == 2


def test_run_once_uses_configured_fee_bps(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [], fee_bps="0")

    result = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    fills = _ledger(config).fetch_all("select * from paper_fills")
    assert result.paper_fills == 2
    assert {Decimal(fill["fee"]) for fill in fills} == {Decimal("0")}


def test_run_once_does_not_duplicate_existing_filled_opportunity(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])
    now = datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc)

    first = run_once(config, now=now)
    second = run_once(config, now=now)

    ledger = _ledger(config)
    assert first.paper_fills == 2
    assert second.opportunities_seen == 1
    assert second.approved_trades == 0
    assert second.rejected_trades == 0
    assert second.paper_fills == 0
    assert len(ledger.fetch_all("select * from paper_fills")) == 2


def test_run_once_skips_opportunity_with_existing_one_sided_fill(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])
    ledger = _ledger(config)
    ledger.initialize()
    first = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )
    fills = ledger.fetch_all("select * from paper_fills order by side")
    with sqlite3.connect(config.ledger_path) as conn:
        conn.execute("delete from paper_fills where side = 'sell'")
        conn.execute("delete from risk_decisions where side = 'sell'")

    second = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    assert first.paper_fills == 2
    assert len(fills) == 2
    assert second.approved_trades == 0
    assert second.rejected_trades == 0
    assert second.paper_fills == 0
    remaining = ledger.fetch_all("select * from paper_fills")
    assert len(remaining) == 1
    assert remaining[0]["side"] == "buy"


def test_run_once_allows_same_prices_at_new_observation_time(tmp_path) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    first = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
    )

    config = _config(
        tmp_path,
        _market_observed_at("2026-05-13T12:00:30Z"),
        [],
    )
    second = run_once(
        config,
        now=datetime(2026, 5, 13, 12, 0, 40, tzinfo=timezone.utc),
    )

    ledger = _ledger(config)
    assert first.paper_fills == 2
    assert second.paper_fills == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 4


def test_concurrent_run_once_does_not_duplicate_same_opportunity(
    monkeypatch,
    tmp_path,
) -> None:
    import stable_coin_trader.engine as engine_module

    config = _config(tmp_path, _profitable_market(), [])
    now = datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc)
    barrier = Barrier(2)
    original_check = engine_module._opportunity_already_filled

    def synchronized_duplicate_check(ledger, opportunity):
        result = original_check(ledger, opportunity)
        barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(
        engine_module,
        "_opportunity_already_filled",
        synchronized_duplicate_check,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_once(config, now=now), range(2)))

    ledger = _ledger(config)
    assert sorted(result.approved_trades for result in results) == [0, 2]
    assert sum(result.paper_fills for result in results) == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 2


def test_run_once_aborts_when_existing_exposure_cannot_be_read(
    monkeypatch,
    tmp_path,
) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    class BrokenExposureLedger(Ledger):
        def fetch_all(self, sql: str):
            if "from paper_fills" in sql:
                raise sqlite3.OperationalError("paper_fills unavailable")
            return super().fetch_all(sql)

    monkeypatch.setattr("stable_coin_trader.engine.Ledger", BrokenExposureLedger)

    with pytest.raises(sqlite3.OperationalError):
        run_once(
            config,
            now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
        )


def test_run_once_rolls_back_pair_when_second_fill_write_fails(
    monkeypatch,
    tmp_path,
) -> None:
    config = _config(tmp_path, _profitable_market(), [])

    class FailingSecondFillLedger(Ledger):
        def __init__(self, path) -> None:
            super().__init__(path)
            self.fill_attempts = 0

        def _insert_paper_fill(self, *args, **kwargs) -> int:
            self.fill_attempts += 1
            if self.fill_attempts == 2:
                raise RuntimeError("simulated second fill failure")
            return super()._insert_paper_fill(*args, **kwargs)

    monkeypatch.setattr("stable_coin_trader.engine.Ledger", FailingSecondFillLedger)

    with pytest.raises(RuntimeError, match="simulated second fill failure"):
        run_once(
            config,
            now=datetime(2026, 5, 13, 12, 0, 10, tzinfo=timezone.utc),
        )

    ledger = _ledger(config)
    assert ledger.fetch_all("select * from risk_decisions") == []
    assert ledger.fetch_all("select * from paper_fills") == []
