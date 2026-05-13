from decimal import Decimal

import pytest

from stable_coin_trader.config import BotConfig
from stable_coin_trader.models import Opportunity, ProposedTrade, ResearchSignal
from stable_coin_trader.risk import RiskEngine


def make_config(**overrides: object) -> BotConfig:
    values: dict[str, object] = {
        "mode": "paper",
        "ledger_path": "paper.sqlite3",
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
    values.update(overrides)
    return BotConfig(**values)


def make_opportunity(
    net_edge_case: str = "profitable",
    **overrides: object,
) -> Opportunity:
    sell_price = {
        "profitable": Decimal("1.0000"),
        "weak": Decimal("0.9997"),
        "tight": Decimal("0.9999"),
    }[net_edge_case]
    values: dict[str, object] = {
        "id": "opp-1",
        "buy_venue": "kraken",
        "sell_venue": "coinbase",
        "symbol": "USDC/USD",
        "size": Decimal("1000"),
        "buy_price": Decimal("0.9995"),
        "sell_price": sell_price,
        "estimated_fees": Decimal("0.10"),
        "estimated_slippage": Decimal("0.02"),
        "observed_at": "2026-05-13T12:00:00Z",
    }
    values.update(overrides)
    return Opportunity(**values)


def make_trade(opportunity: Opportunity, **overrides: object) -> ProposedTrade:
    values: dict[str, object] = {
        "opportunity_id": opportunity.id,
        "side": "buy",
        "venue": opportunity.buy_venue,
        "symbol": opportunity.symbol,
        "size": opportunity.size,
        "limit_price": opportunity.buy_price,
    }
    values.update(overrides)
    return ProposedTrade(**values)


def make_signal(**overrides: object) -> ResearchSignal:
    values: dict[str, object] = {
        "id": "sig-1",
        "observed_at": "2026-05-13T12:00:00Z",
        "published_at": "2026-05-13T11:59:00Z",
        "source": "fixture",
        "source_url": "https://example.com/signal",
        "source_quality": 0.9,
        "affected_assets": ["USDC"],
        "affected_venues": ["kraken"],
        "event_type": "withdrawal_delay",
        "direction": "risk_increase",
        "severity": 5,
        "confidence": 0.9,
        "ttl_seconds": 3600,
        "human_review_required": False,
        "summary": "High severity withdrawal delay.",
    }
    values.update(overrides)
    return ResearchSignal(**values)


def test_risk_engine_approves_trade_above_min_edge() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is True
    assert decision.reason == "approved"


def test_risk_engine_rejects_trade_below_min_edge() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="weak")
    trade = make_trade(opportunity)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.min_edge_bps == Decimal("2.5")


def test_risk_engine_rejects_when_research_requires_review() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    signal = make_signal(id="sig-1", human_review_required=True)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[signal])

    assert decision.approved is False
    assert decision.reason == "human review required by research signal"
    assert decision.requires_human_approval is True
    assert decision.active_signal_ids == ["sig-1"]


def test_risk_engine_rejects_order_above_max_order() -> None:
    engine = RiskEngine(make_config(max_order_usd="999", max_position_usd="5000"))
    opportunity = make_opportunity()
    trade = make_trade(opportunity)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "order exceeds max order size"


def test_risk_engine_rejects_order_above_max_position() -> None:
    engine = RiskEngine(make_config(max_order_usd="1000", max_position_usd="1000"))
    opportunity = make_opportunity()
    trade = make_trade(opportunity)

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[],
        current_position_usd=Decimal("1"),
    )

    assert decision.approved is False
    assert decision.reason == "order exceeds max position size"


def test_risk_increase_signal_tightens_min_edge_and_can_reject_trade() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="tight")
    trade = make_trade(opportunity)
    signal = make_signal(
        id="sig-tighten",
        severity=4,
        confidence=0.5,
        source_quality=1.0,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[signal])

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.min_edge_bps == Decimal("4.5")
    assert decision.active_signal_ids == ["sig-tighten"]


def test_risk_decrease_signal_cannot_loosen_min_edge() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="weak")
    trade = make_trade(opportunity)
    signal = make_signal(
        id="sig-decrease",
        direction="risk_decrease",
        severity=5,
        confidence=1.0,
        source_quality=1.0,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[signal])

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.min_edge_bps == Decimal("2.5")
    assert decision.active_signal_ids == []


def test_risk_increase_signals_scope_by_base_asset_or_trade_venue() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="tight")
    trade = make_trade(opportunity)
    asset_signal = make_signal(
        id="asset-a",
        affected_assets=["USDC"],
        affected_venues=["gemini"],
        severity=1,
        confidence=1.0,
        source_quality=1.0,
    )
    venue_signal = make_signal(
        id="venue-b",
        affected_assets=["USDT"],
        affected_venues=["kraken"],
        severity=1,
        confidence=1.0,
        source_quality=1.0,
    )
    unscoped_signal = make_signal(
        id="unscoped",
        affected_assets=["USD"],
        affected_venues=["gemini"],
        severity=5,
        confidence=1.0,
        source_quality=1.0,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[unscoped_signal, venue_signal, asset_signal],
    )

    assert decision.approved is False
    assert decision.min_edge_bps == Decimal("4.5")
    assert decision.active_signal_ids == ["asset-a", "venue-b"]


def test_neutral_and_risk_decrease_signals_without_review_are_ignored_for_tightening() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    neutral_signal = make_signal(
        id="neutral",
        direction="neutral",
        human_review_required=False,
    )
    decrease_signal = make_signal(
        id="decrease",
        direction="risk_decrease",
        severity=5,
        confidence=1.0,
        source_quality=1.0,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[neutral_signal, decrease_signal],
    )

    assert decision.approved is True
    assert decision.min_edge_bps == Decimal("2.5")
    assert decision.requires_human_approval is False
    assert decision.active_signal_ids == []


def test_human_review_blocks_when_scoped_even_if_signal_is_neutral() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    neutral_signal = make_signal(
        id="neutral-review",
        direction="neutral",
        human_review_required=True,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[neutral_signal],
    )

    assert decision.approved is False
    assert decision.reason == "human review required by research signal"
    assert decision.requires_human_approval is True
    assert decision.active_signal_ids == ["neutral-review"]


def test_human_review_blocks_when_signal_scopes_to_opposite_opportunity_venue() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    sell_venue_signal = make_signal(
        id="sell-venue-review",
        affected_assets=["USDT"],
        affected_venues=[opportunity.sell_venue],
        human_review_required=True,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[sell_venue_signal],
    )

    assert decision.approved is False
    assert decision.requires_human_approval is True
    assert decision.active_signal_ids == ["sell-venue-review"]


def test_human_review_ignores_unscoped_signal() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    unscoped_signal = make_signal(
        id="unscoped-review",
        affected_assets=["USDT"],
        affected_venues=["gemini"],
        human_review_required=True,
    )
    neutral_signal = make_signal(
        id="neutral-review",
        direction="neutral",
        affected_assets=["USDT"],
        affected_venues=["gemini"],
        human_review_required=True,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[unscoped_signal, neutral_signal],
    )

    assert decision.approved is True
    assert decision.requires_human_approval is False
    assert decision.active_signal_ids == []


def test_risk_increase_signal_scopes_to_opposite_opportunity_venue() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="tight")
    trade = make_trade(opportunity)
    sell_venue_signal = make_signal(
        id="coinbase-risk",
        affected_assets=["USDT"],
        affected_venues=[opportunity.sell_venue],
        severity=3,
        confidence=1.0,
        source_quality=1.0,
    )

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[sell_venue_signal],
    )

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.min_edge_bps == Decimal("5.5")
    assert decision.active_signal_ids == ["coinbase-risk"]


@pytest.mark.parametrize(
    "opportunity_overrides",
    [
        {"symbol": "USDT/USD"},
        {"buy_venue": "gemini"},
        {"sell_venue": "gemini"},
    ],
)
def test_risk_engine_rejects_unconfigured_trading_universe(
    opportunity_overrides: dict[str, object],
) -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(**opportunity_overrides)
    trade = make_trade(opportunity)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "trade outside configured universe"


@pytest.mark.parametrize(
    "trade_overrides",
    [
        {"opportunity_id": "other-opp"},
        {"venue": "coinbase"},
        {"symbol": "USDT/USD"},
        {"size": Decimal("999")},
        {"limit_price": Decimal("0.9994")},
    ],
)
def test_trade_opportunity_mismatch_fails_closed(
    trade_overrides: dict[str, object],
) -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity, **trade_overrides)

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "trade does not match opportunity"


def test_sell_trade_must_match_sell_leg() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(
        opportunity,
        side="sell",
        venue=opportunity.sell_venue,
        limit_price=opportunity.sell_price,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is True


def test_unexpected_trade_side_fails_closed() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = ProposedTrade.model_construct(
        opportunity_id=opportunity.id,
        side="hold",
        venue=opportunity.sell_venue,
        symbol=opportunity.symbol,
        size=opportunity.size,
        limit_price=opportunity.sell_price,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "trade does not match opportunity"


def test_active_signal_ids_are_sorted_deterministically() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = make_trade(opportunity)
    signal_b = make_signal(id="sig-b", severity=0)
    signal_a = make_signal(id="sig-a", severity=0)

    decision = engine.evaluate(
        trade=trade,
        opportunity=opportunity,
        signals=[signal_b, signal_a],
    )

    assert decision.active_signal_ids == ["sig-a", "sig-b"]
