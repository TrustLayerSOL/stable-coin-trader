import json
import sqlite3
from datetime import datetime
from decimal import Decimal

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
