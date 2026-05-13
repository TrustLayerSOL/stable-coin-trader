from decimal import Decimal

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import ProposedTrade, RiskDecision


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
        active_signal_ids=["sig-1"],
    )

    decision_id = ledger.record_risk_decision(decision)
    rows = ledger.fetch_all("select * from risk_decisions")

    assert decision_id > 0
    assert len(rows) == 1
    assert rows[0]["approved"] == 1
    assert rows[0]["reason"] == "net edge meets threshold"
    assert rows[0]["active_signal_ids"] == "sig-1"


def test_ledger_records_paper_fill(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.initialize()

    fill_id = ledger.record_paper_fill(
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
    assert rows[0]["venue"] == "kraken"
    assert rows[0]["fee"] == "0.20"
