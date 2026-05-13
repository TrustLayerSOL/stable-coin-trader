from decimal import Decimal

import pytest

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import ProposedTrade, RiskDecision
from stable_coin_trader.paper import PaperExecutor


def _trade() -> ProposedTrade:
    return ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )


def _sell_trade() -> ProposedTrade:
    return ProposedTrade(
        opportunity_id="opp-1",
        side="sell",
        venue="coinbase",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("1.0002"),
    )


def _initialized_ledger(tmp_path) -> Ledger:
    ledger = Ledger(tmp_path / "paper.sqlite3")
    ledger.initialize()
    return ledger


def test_paper_executor_records_fill_for_approved_trade(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
    decision = RiskDecision.approve(
        trade=_trade(),
        reason="approved",
        min_edge_bps=Decimal("2.5"),
    )

    fill_id = executor.execute(decision)

    risk_rows = ledger.fetch_all("select * from risk_decisions")
    fill_rows = ledger.fetch_all("select * from paper_fills")
    assert fill_id is not None
    assert len(risk_rows) == 1
    assert len(fill_rows) == 1
    assert fill_rows[0]["id"] == fill_id
    assert fill_rows[0]["risk_decision_id"] == risk_rows[0]["id"]
    assert fill_rows[0]["opportunity_id"] == "opp-1"
    assert fill_rows[0]["venue"] == "kraken"
    assert fill_rows[0]["symbol"] == "USDC/USD"
    assert Decimal(fill_rows[0]["fee"]) == Decimal("0.09995")


def test_paper_executor_does_not_fill_rejected_trade_but_records_decision(
    tmp_path,
) -> None:
    ledger = _initialized_ledger(tmp_path)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
    decision = RiskDecision.reject(trade=_trade(), reason="blocked")

    fill_id = executor.execute(decision)

    risk_rows = ledger.fetch_all("select * from risk_decisions")
    assert fill_id is None
    assert len(risk_rows) == 1
    assert risk_rows[0]["approved"] == 0
    assert risk_rows[0]["reason"] == "blocked"
    assert ledger.fetch_all("select * from paper_fills") == []


def test_paper_executor_does_not_fill_human_review_rejected_trade(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
    decision = RiskDecision.reject(
        trade=_trade(),
        reason="human review required by research signal",
        requires_human_approval=True,
        active_signal_ids=["signal-1"],
    )

    fill_id = executor.execute(decision)

    risk_rows = ledger.fetch_all("select * from risk_decisions")
    assert fill_id is None
    assert len(risk_rows) == 1
    assert risk_rows[0]["approved"] == 0
    assert risk_rows[0]["requires_human_approval"] == 1
    assert ledger.fetch_all("select * from paper_fills") == []


def test_paper_executor_supports_zero_fees(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("0"))
    decision = RiskDecision.approve(
        trade=_trade(),
        reason="approved",
        min_edge_bps=Decimal("2.5"),
    )

    fill_id = executor.execute(decision)

    fill_rows = ledger.fetch_all("select * from paper_fills")
    assert fill_id is not None
    assert Decimal(fill_rows[0]["fee"]) == Decimal("0")


def test_paper_executor_executes_approved_batch_atomically(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
    decisions = [
        RiskDecision.approve(
            trade=_trade(),
            reason="approved",
            min_edge_bps=Decimal("2.5"),
        ),
        RiskDecision.approve(
            trade=_sell_trade(),
            reason="approved",
            min_edge_bps=Decimal("2.5"),
        ),
    ]

    fill_ids = executor.execute_many(decisions)

    assert len(fill_ids) == 2
    assert len(ledger.fetch_all("select * from risk_decisions")) == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 2


@pytest.mark.parametrize(
    "fee_bps",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_paper_executor_rejects_negative_or_nonfinite_fee_bps(fee_bps) -> None:
    with pytest.raises(ValueError, match="fee_bps must be nonnegative and finite"):
        PaperExecutor(ledger=Ledger(":memory:"), fee_bps=fee_bps)


def test_paper_executor_rejects_non_decimal_fee_bps() -> None:
    with pytest.raises(TypeError, match="fee_bps must be a Decimal"):
        PaperExecutor(ledger=Ledger(":memory:"), fee_bps=1)
