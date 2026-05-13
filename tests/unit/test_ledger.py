import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Barrier, BrokenBarrierError

import pytest

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import ProposedTrade, RiskDecision


def _record_approved_decision(ledger: Ledger) -> int:
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    return ledger.record_risk_decision(
        RiskDecision.approve(
            trade=trade,
            reason="net edge meets threshold",
            min_edge_bps=Decimal("2.5"),
        )
    )


def _record_rejected_decision(ledger: Ledger) -> int:
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    return ledger.record_risk_decision(
        RiskDecision.reject(
            trade=trade,
            reason="signal requires human review",
            min_edge_bps=Decimal("5"),
            requires_human_approval=True,
        )
    )


class _BarrierLedger(Ledger):
    def __init__(self, path, barrier: Barrier) -> None:
        super().__init__(path)
        self.barrier = barrier

    def _validate_paper_fill_matches_decision(self, *args, **kwargs) -> None:
        super()._validate_paper_fill_matches_decision(*args, **kwargs)
        try:
            self.barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass


def test_ledger_records_risk_decision(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    decision = RiskDecision.approve(
        trade=trade,
        reason="net edge meets threshold",
        min_edge_bps=Decimal("2.5"),
        active_signal_ids=["sig-1", "sig-2"],
    )

    decision_id = ledger.record_risk_decision(decision)
    rows = ledger.fetch_all("select * from risk_decisions")

    assert decision_id > 0
    assert len(rows) == 1
    row = rows[0]
    created_at = datetime.fromisoformat(row["created_at"])
    assert created_at.tzinfo is not None
    assert row["id"] == decision_id
    assert row["opportunity_id"] == "opp-1"
    assert row["venue"] == "kraken"
    assert row["symbol"] == "USDC/USD"
    assert row["side"] == "buy"
    assert row["size"] == "1000"
    assert row["limit_price"] == "0.9995"
    assert row["approved"] == 1
    assert row["reason"] == "net edge meets threshold"
    assert row["min_edge_bps"] == "2.5"
    assert row["requires_human_approval"] == 0
    assert json.loads(row["active_signal_ids"]) == ["sig-1", "sig-2"]


def test_ledger_records_rejected_human_review_risk_decision(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    trade = ProposedTrade(
        opportunity_id="opp-review",
        side="sell",
        venue="coinbase",
        symbol="USDT/USD",
        size=Decimal("250"),
        limit_price=Decimal("1.0001"),
    )
    decision = RiskDecision.reject(
        trade=trade,
        reason="fresh venue outage signal requires review",
        min_edge_bps=Decimal("5"),
        requires_human_approval=True,
        active_signal_ids=["outage-1", "liquidity-2"],
    )

    decision_id = ledger.record_risk_decision(decision)
    rows = ledger.fetch_all("select * from risk_decisions")

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == decision_id
    assert row["opportunity_id"] == "opp-review"
    assert row["venue"] == "coinbase"
    assert row["symbol"] == "USDT/USD"
    assert row["side"] == "sell"
    assert row["size"] == "250"
    assert row["limit_price"] == "1.0001"
    assert row["approved"] == 0
    assert row["reason"] == "fresh venue outage signal requires review"
    assert row["min_edge_bps"] == "5"
    assert row["requires_human_approval"] == 1
    assert json.loads(row["active_signal_ids"]) == ["outage-1", "liquidity-2"]


def test_ledger_records_paper_fill(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    fill_id = ledger.record_paper_fill(
        risk_decision_id=decision_id,
        opportunity_id="opp-1",
        venue="kraken",
        symbol="USDC/USD",
        side="buy",
        size=Decimal("1000"),
        price=Decimal("0.9995"),
        fee=Decimal("0.20"),
    )
    rows = ledger.fetch_all("select * from paper_fills")

    assert fill_id > 0
    assert len(rows) == 1
    row = rows[0]
    created_at = datetime.fromisoformat(row["created_at"])
    assert created_at.tzinfo is not None
    assert row["id"] == fill_id
    assert row["risk_decision_id"] == decision_id
    assert row["opportunity_id"] == "opp-1"
    assert row["venue"] == "kraken"
    assert row["symbol"] == "USDC/USD"
    assert row["side"] == "buy"
    assert row["size"] == "1000"
    assert row["price"] == "0.9995"
    assert row["fee"] == "0.20"


def test_ledger_rejects_paper_fill_with_unknown_risk_decision_id(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()

    with pytest.raises(sqlite3.IntegrityError):
        ledger.record_paper_fill(
            risk_decision_id=999,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("1000"),
            price=Decimal("0.9995"),
            fee=Decimal("0.20"),
        )


@pytest.mark.parametrize(
    ("size", "price", "fee", "message"),
    [
        (Decimal("0"), Decimal("0.9995"), Decimal("0.20"), "size"),
        (Decimal("-1"), Decimal("0.9995"), Decimal("0.20"), "size"),
        (Decimal("1"), Decimal("0"), Decimal("0.20"), "price"),
        (Decimal("1"), Decimal("-0.9995"), Decimal("0.20"), "price"),
        (Decimal("1"), Decimal("0.9995"), Decimal("-0.01"), "fee"),
        (Decimal("NaN"), Decimal("0.9995"), Decimal("0.20"), "size"),
        (Decimal("1"), Decimal("Infinity"), Decimal("0.20"), "price"),
        (Decimal("1"), Decimal("0.9995"), Decimal("-Infinity"), "fee"),
    ],
)
def test_ledger_rejects_invalid_paper_fill_numbers(
    tmp_path,
    size,
    price,
    fee,
    message,
) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    with pytest.raises(ValueError, match=message):
        ledger.record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=size,
            price=price,
            fee=fee,
        )


def test_ledger_rejects_paper_fill_for_rejected_risk_decision(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_rejected_decision(ledger)

    with pytest.raises(ValueError, match="approved"):
        ledger.record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("1000"),
            price=Decimal("0.9995"),
            fee=Decimal("0.20"),
        )


def test_ledger_rejects_paper_fill_with_mismatched_venue(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    with pytest.raises(ValueError, match="venue"):
        ledger.record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="coinbase",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("1000"),
            price=Decimal("0.9995"),
            fee=Decimal("0.20"),
        )


def test_ledger_rejects_paper_fill_with_mismatched_price(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    with pytest.raises(ValueError, match="price"):
        ledger.record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("1000"),
            price=Decimal("1.0000"),
            fee=Decimal("0.20"),
        )


def test_ledger_allows_partial_fill_with_numeric_scale_difference(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    ledger.record_paper_fill(
        risk_decision_id=decision_id,
        opportunity_id="opp-1",
        venue="kraken",
        symbol="USDC/USD",
        side="buy",
        size=Decimal("1000.00"),
        price=Decimal("0.99950"),
        fee=Decimal("0.20"),
    )

    rows = ledger.fetch_all("select * from paper_fills")
    assert len(rows) == 1
    assert rows[0]["size"] == "1000.00"
    assert rows[0]["price"] == "0.99950"


def test_ledger_allows_buy_fill_below_limit_price(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    fill_id = ledger.record_paper_fill(
        risk_decision_id=decision_id,
        opportunity_id="opp-1",
        venue="kraken",
        symbol="USDC/USD",
        side="buy",
        size=Decimal("500"),
        price=Decimal("0.9994"),
        fee=Decimal("0.10"),
    )

    assert fill_id > 0


def test_ledger_rejects_fill_that_exceeds_approved_size(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)
    ledger.record_paper_fill(
        risk_decision_id=decision_id,
        opportunity_id="opp-1",
        venue="kraken",
        symbol="USDC/USD",
        side="buy",
        size=Decimal("600"),
        price=Decimal("0.9995"),
        fee=Decimal("0.12"),
    )

    with pytest.raises(ValueError, match="size"):
        ledger.record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("500"),
            price=Decimal("0.9995"),
            fee=Decimal("0.10"),
        )


def test_ledger_serializes_fill_size_validation(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    ledger = Ledger(path)
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)
    barrier = Barrier(2)

    def record_competing_fill():
        return _BarrierLedger(path, barrier).record_paper_fill(
            risk_decision_id=decision_id,
            opportunity_id="opp-1",
            venue="kraken",
            symbol="USDC/USD",
            side="buy",
            size=Decimal("600"),
            price=Decimal("0.9995"),
            fee=Decimal("0.12"),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [
            future.exception()
            for future in (
                executor.submit(record_competing_fill),
                executor.submit(record_competing_fill),
            )
        ]

    rows = ledger.fetch_all("select * from paper_fills")
    assert len(rows) == 1
    assert sum(Decimal(row["size"]) for row in rows) <= Decimal("1000")
    assert sum(error is None for error in outcomes) == 1
    assert any(
        isinstance(error, ValueError) and "size" in str(error)
        for error in outcomes
    )


def test_ledger_upgrades_empty_legacy_paper_fill_schema(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table risk_decisions (
                id integer primary key autoincrement,
                created_at text not null,
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text not null,
                limit_price text not null,
                approved integer not null,
                reason text not null,
                min_edge_bps text not null,
                requires_human_approval integer not null,
                active_signal_ids text not null
            );
            create table paper_fills (
                id integer primary key autoincrement,
                created_at text not null,
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text not null,
                price text not null,
                fee text not null
            );
            """
        )

    ledger = Ledger(path)
    ledger.initialize()

    columns = [row["name"] for row in ledger.fetch_all("pragma table_info(paper_fills)")]
    assert "risk_decision_id" in columns


def test_ledger_rebuilds_empty_malformed_paper_fill_schema(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table risk_decisions (
                id integer primary key autoincrement,
                created_at text not null,
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text not null,
                limit_price text not null,
                approved integer not null,
                reason text not null,
                min_edge_bps text not null,
                requires_human_approval integer not null,
                active_signal_ids text not null
            );
            create table paper_fills (
                id integer primary key autoincrement,
                created_at text not null,
                risk_decision_id integer not null references risk_decisions(id),
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text,
                price text not null,
                fee text not null
            );
            """
        )

    ledger = Ledger(path)
    ledger.initialize()

    columns = {
        row["name"]: row
        for row in ledger.fetch_all("pragma table_info(paper_fills)")
    }
    assert columns["size"]["notnull"] == 1


def test_ledger_rejects_nonempty_legacy_paper_fill_schema(tmp_path) -> None:
    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table risk_decisions (
                id integer primary key autoincrement,
                created_at text not null,
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text not null,
                limit_price text not null,
                approved integer not null,
                reason text not null,
                min_edge_bps text not null,
                requires_human_approval integer not null,
                active_signal_ids text not null
            );
            create table paper_fills (
                id integer primary key autoincrement,
                created_at text not null,
                opportunity_id text not null,
                venue text not null,
                symbol text not null,
                side text not null,
                size text not null,
                price text not null,
                fee text not null
            );
            insert into paper_fills (
                created_at, opportunity_id, venue, symbol, side, size, price, fee
            ) values (
                '2026-05-13T12:00:00+00:00', 'opp-legacy', 'kraken',
                'USDC/USD', 'buy', '1000', '0.9995', '0.20'
            );
            """
        )

    ledger = Ledger(path)

    with pytest.raises(RuntimeError, match="legacy"):
        ledger.initialize()


def test_ledger_fetch_all_is_read_only(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()
    decision_id = _record_approved_decision(ledger)

    with pytest.raises(ValueError, match="read-only"):
        ledger.fetch_all("delete from risk_decisions")
    with pytest.raises(ValueError, match="read-only"):
        ledger.fetch_all("pragma user_version = 3")

    rows = ledger.fetch_all("select * from risk_decisions")
    assert len(rows) == 1
    assert rows[0]["id"] == decision_id
    assert ledger.fetch_all("pragma user_version")[0]["user_version"] == 0
