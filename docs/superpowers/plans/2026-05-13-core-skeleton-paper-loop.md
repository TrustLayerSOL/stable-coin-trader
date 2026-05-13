# Core Skeleton Paper Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first testable slice of the risk-aware stablecoin trader: Python package, config, ledger, risk engine, opportunity engine, research signal model, paper execution, and a fixture-driven CLI.

**Architecture:** This plan creates a modular Python core with no live exchange access. Market data and research signals enter through local fixture files so the trading loop can be tested deterministically before any external APIs or real money are connected. The risk engine is authoritative, the opportunity engine only proposes trades, and the paper executor records all decisions and simulated fills in SQLite.

**Tech Stack:** Python 3.12, pytest, pydantic, Typer, Rich, SQLite via the standard library.

---

## Scope Check

The full design spec covers multiple independent subsystems: CEX adapters, DEX support, research APIs, live trading, monitoring, and later yield routing. This plan implements only the first working slice:

- Local package and test harness.
- Safety-first config.
- Core domain models.
- SQLite ledger.
- Deterministic fixture market data.
- Deterministic fixture research signals.
- Stablecoin spread opportunity detection.
- Risk approval and rejection.
- Paper execution and audit trail.
- CLI command that runs one paper cycle.

Live trading, real exchange APIs, DEX execution, dashboards, and paid data APIs will get separate plans after this slice passes.

## File Structure

Create:

- `.gitignore`: ignore secrets, virtualenvs, caches, and local databases.
- `README.md`: short operator-facing project description.
- `pyproject.toml`: Python package metadata, dependencies, pytest config.
- `config/paper.example.json`: safe example config.
- `data/fixtures/market_snapshots.json`: deterministic market data input.
- `data/fixtures/research_signals.json`: deterministic research signal input.
- `src/stable_coin_trader/__init__.py`: package version.
- `src/stable_coin_trader/__main__.py`: module entrypoint.
- `src/stable_coin_trader/cli.py`: Typer CLI.
- `src/stable_coin_trader/config.py`: config models and loader.
- `src/stable_coin_trader/models.py`: shared domain models.
- `src/stable_coin_trader/ledger.py`: SQLite ledger and schema.
- `src/stable_coin_trader/market_data.py`: fixture market data loader.
- `src/stable_coin_trader/research.py`: fixture research signal loader and expiration handling.
- `src/stable_coin_trader/opportunities.py`: spread opportunity calculation.
- `src/stable_coin_trader/risk.py`: risk constraint evaluation.
- `src/stable_coin_trader/paper.py`: paper executor.
- `src/stable_coin_trader/engine.py`: one-cycle orchestration.
- `tests/unit/test_config.py`
- `tests/unit/test_models.py`
- `tests/unit/test_ledger.py`
- `tests/unit/test_market_data.py`
- `tests/unit/test_research.py`
- `tests/unit/test_opportunities.py`
- `tests/unit/test_risk.py`
- `tests/unit/test_paper.py`
- `tests/integration/test_engine_cycle.py`

Modify:

- `PROJECT.md`: update current status and add the implementation plan path.
- `PROJECT_LOG.md`: add an entry for this implementation plan.

## Task 1: Python Project Bootstrap

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `src/stable_coin_trader/__init__.py`
- Create: `src/stable_coin_trader/__main__.py`
- Create: `src/stable_coin_trader/cli.py`
- Create: `tests/unit/test_package.py`

- [ ] **Step 1: Write the failing package import test**

Create `tests/unit/test_package.py`:

```python
from stable_coin_trader import __version__


def test_package_has_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/unit/test_package.py -v
```

Expected: FAIL because `stable_coin_trader` is not importable.

- [ ] **Step 3: Create project metadata and package files**

Create `.gitignore`:

```gitignore
.DS_Store
.env
.env.*
!.env.example
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.pyc
*.db
*.sqlite
*.sqlite3
dist/
build/
*.egg-info/
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stable-coin-trader"
version = "0.1.0"
description = "Risk-aware stablecoin paper trading bot for proprietary capital."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.7,<3",
  "typer>=0.12,<1",
  "rich>=13.7,<14"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9"
]

[project.scripts]
stable-coin-trader = "stable_coin_trader.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
```

Create `README.md`:

```markdown
# Stable Coin Trader

Risk-aware stablecoin paper trading bot for proprietary capital.

Current phase: core skeleton and deterministic paper loop. The project does not contain live trading code yet.

Safety rules:

- No secrets in git.
- Paper mode first.
- Risk engine approves every proposed trade.
- Research signals can reduce risk, pause trading, or require review, but cannot originate trades.
```

Create `src/stable_coin_trader/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/stable_coin_trader/cli.py`:

```python
import typer

app = typer.Typer(help="Risk-aware stablecoin paper trading bot.")


@app.callback()
def main() -> None:
    """Stable Coin Trader command line interface."""
```

Create `src/stable_coin_trader/__main__.py`:

```python
from stable_coin_trader.cli import app


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/unit/test_package.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md pyproject.toml src/stable_coin_trader/__init__.py src/stable_coin_trader/__main__.py src/stable_coin_trader/cli.py tests/unit/test_package.py
git commit -m "chore: bootstrap python project"
```

## Task 2: Core Domain Models

**Files:**
- Create: `src/stable_coin_trader/models.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/unit/test_models.py`:

```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from stable_coin_trader.models import (
    MarketSnapshot,
    Opportunity,
    ProposedTrade,
    ResearchSignal,
    RiskDecision,
)


def test_market_snapshot_calculates_mid_price() -> None:
    snapshot = MarketSnapshot(
        venue="coinbase",
        symbol="USDC/USD",
        bid=Decimal("0.9998"),
        ask=Decimal("1.0000"),
        bid_size=Decimal("50000"),
        ask_size=Decimal("75000"),
        observed_at="2026-05-13T12:00:00Z",
    )

    assert snapshot.mid_price == Decimal("0.9999")


def test_market_snapshot_rejects_crossed_book() -> None:
    with pytest.raises(ValidationError):
        MarketSnapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid=Decimal("1.0001"),
            ask=Decimal("1.0000"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("75000"),
            observed_at="2026-05-13T12:00:00Z",
        )


def test_opportunity_net_edge_bps() -> None:
    opportunity = Opportunity(
        buy_venue="kraken",
        sell_venue="coinbase",
        symbol="USDC/USD",
        size=Decimal("1000"),
        buy_price=Decimal("0.9995"),
        sell_price=Decimal("1.0000"),
        estimated_fees=Decimal("0.40"),
        estimated_slippage=Decimal("0.05"),
        observed_at="2026-05-13T12:00:00Z",
    )

    assert opportunity.gross_profit == Decimal("0.5000")
    assert opportunity.net_profit == Decimal("0.0500")
    assert opportunity.net_edge_bps == Decimal("0.5000")


def test_research_signal_requires_valid_direction() -> None:
    with pytest.raises(ValidationError):
        ResearchSignal(
            id="sig-1",
            observed_at="2026-05-13T12:00:00Z",
            published_at="2026-05-13T11:59:00Z",
            source="fixture",
            source_url="https://example.com/signal",
            source_quality=0.7,
            affected_assets=["USDC"],
            affected_venues=["coinbase"],
            event_type="venue_outage",
            direction="buy_now",
            severity=3,
            confidence=0.8,
            ttl_seconds=3600,
            summary="Invalid direction should fail.",
        )


def test_risk_decision_explains_rejection() -> None:
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    decision = RiskDecision.reject(trade=trade, reason="net edge below minimum")

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"
    assert decision.requires_human_approval is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_models.py -v
```

Expected: FAIL because `stable_coin_trader.models` does not exist.

- [ ] **Step 3: Implement domain models**

Create `src/stable_coin_trader/models.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class MarketSnapshot(BaseModel):
    venue: str
    symbol: str
    bid: Decimal
    ask: Decimal
    bid_size: Decimal
    ask_size: Decimal
    observed_at: datetime

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_at(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @model_validator(mode="after")
    def validate_book(self) -> "MarketSnapshot":
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.bid > self.ask:
            raise ValueError("bid cannot be greater than ask")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("book sizes cannot be negative")
        return self

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    buy_venue: str
    sell_venue: str
    symbol: str
    size: Decimal
    buy_price: Decimal
    sell_price: Decimal
    estimated_fees: Decimal
    estimated_slippage: Decimal
    observed_at: datetime

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_at(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    @property
    def gross_profit(self) -> Decimal:
        return (self.sell_price - self.buy_price) * self.size

    @property
    def net_profit(self) -> Decimal:
        return self.gross_profit - self.estimated_fees - self.estimated_slippage

    @property
    def notional(self) -> Decimal:
        return self.buy_price * self.size

    @property
    def net_edge_bps(self) -> Decimal:
        if self.notional <= 0:
            return Decimal("0")
        return (self.net_profit / self.notional) * Decimal("10000")


class ProposedTrade(BaseModel):
    opportunity_id: str
    side: Literal["buy", "sell"]
    venue: str
    symbol: str
    size: Decimal
    limit_price: Decimal


class ResearchSignal(BaseModel):
    id: str
    observed_at: datetime
    published_at: datetime
    source: str
    source_url: str
    source_quality: float = Field(ge=0, le=1)
    affected_assets: list[str]
    affected_venues: list[str]
    event_type: Literal[
        "depeg_risk",
        "issuer_reserve",
        "issuer_redemption",
        "venue_outage",
        "withdrawal_delay",
        "regulatory",
        "macro",
        "liquidity",
        "oracle",
        "rumor",
        "social_trend",
        "informational",
    ]
    direction: Literal["risk_increase", "risk_decrease", "neutral"]
    severity: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    ttl_seconds: int = Field(gt=0)
    summary: str
    human_review_required: bool = False

    @field_validator("observed_at", "published_at", mode="before")
    @classmethod
    def parse_datetimes(cls, value: datetime | str) -> datetime:
        return parse_dt(value)

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        current = parse_dt(current)
        age = current - self.observed_at
        return age.total_seconds() > self.ttl_seconds

    @property
    def risk_score(self) -> Decimal:
        return Decimal(str(self.severity * self.confidence * self.source_quality))


class RiskDecision(BaseModel):
    trade: ProposedTrade
    approved: bool
    reason: str
    min_edge_bps: Decimal = Decimal("0")
    requires_human_approval: bool = False
    active_signal_ids: list[str] = Field(default_factory=list)

    @classmethod
    def approve(
        cls,
        trade: ProposedTrade,
        reason: str,
        min_edge_bps: Decimal,
        active_signal_ids: list[str] | None = None,
    ) -> "RiskDecision":
        return cls(
            trade=trade,
            approved=True,
            reason=reason,
            min_edge_bps=min_edge_bps,
            active_signal_ids=active_signal_ids or [],
        )

    @classmethod
    def reject(
        cls,
        trade: ProposedTrade,
        reason: str,
        min_edge_bps: Decimal = Decimal("0"),
        requires_human_approval: bool = False,
        active_signal_ids: list[str] | None = None,
    ) -> "RiskDecision":
        return cls(
            trade=trade,
            approved=False,
            reason=reason,
            min_edge_bps=min_edge_bps,
            requires_human_approval=requires_human_approval,
            active_signal_ids=active_signal_ids or [],
        )
```

- [ ] **Step 4: Run model tests**

Run:

```bash
python -m pytest tests/unit/test_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/models.py tests/unit/test_models.py
git commit -m "feat: add core trading models"
```

## Task 3: Safe Configuration Loader

**Files:**
- Create: `config/paper.example.json`
- Create: `src/stable_coin_trader/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/unit/test_config.py`:

```python
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
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_config.py -v
```

Expected: FAIL because `stable_coin_trader.config` does not exist.

- [ ] **Step 3: Implement config loader**

Create `src/stable_coin_trader/config.py`:

```python
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BotConfig(BaseModel):
    mode: Literal["paper"]
    ledger_path: str
    market_data_path: str
    research_signals_path: str
    base_currency: str = "USD"
    symbols: list[str]
    venues: list[str]
    max_order_usd: Decimal = Field(gt=0)
    max_position_usd: Decimal = Field(gt=0)
    min_edge_bps: Decimal = Field(ge=0)
    stale_after_seconds: int = Field(gt=0)
    depeg_threshold_bps: Decimal = Field(gt=0)
    daily_loss_limit_usd: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_config(self) -> "BotConfig":
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        if not self.venues:
            raise ValueError("at least one venue is required")
        if self.max_order_usd > self.max_position_usd:
            raise ValueError("max_order_usd cannot exceed max_position_usd")
        return self


def load_config(path: str | Path) -> BotConfig:
    config_path = Path(path)
    data = json.loads(config_path.read_text())
    return BotConfig.model_validate(data)
```

Create `config/paper.example.json`:

```json
{
  "mode": "paper",
  "ledger_path": "runtime/paper.sqlite3",
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
  "daily_loss_limit_usd": "25"
}
```

- [ ] **Step 4: Run config tests**

Run:

```bash
python -m pytest tests/unit/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/paper.example.json src/stable_coin_trader/config.py tests/unit/test_config.py
git commit -m "feat: add paper mode configuration"
```

## Task 4: SQLite Ledger

**Files:**
- Create: `src/stable_coin_trader/ledger.py`
- Create: `tests/unit/test_ledger.py`

- [ ] **Step 1: Write failing ledger tests**

Create `tests/unit/test_ledger.py`:

```python
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
```

- [ ] **Step 2: Run ledger tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_ledger.py -v
```

Expected: FAIL because `stable_coin_trader.ledger` does not exist.

- [ ] **Step 3: Implement ledger**

Create `src/stable_coin_trader/ledger.py`:

```python
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from stable_coin_trader.models import RiskDecision, utc_now


class Ledger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists risk_decisions (
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

                create table if not exists paper_fills (
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

    def record_risk_decision(self, decision: RiskDecision) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into risk_decisions (
                    created_at,
                    opportunity_id,
                    venue,
                    symbol,
                    side,
                    size,
                    limit_price,
                    approved,
                    reason,
                    min_edge_bps,
                    requires_human_approval,
                    active_signal_ids
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now().isoformat(),
                    decision.trade.opportunity_id,
                    decision.trade.venue,
                    decision.trade.symbol,
                    decision.trade.side,
                    str(decision.trade.size),
                    str(decision.trade.limit_price),
                    1 if decision.approved else 0,
                    decision.reason,
                    str(decision.min_edge_bps),
                    1 if decision.requires_human_approval else 0,
                    ",".join(decision.active_signal_ids),
                ),
            )
            return int(cursor.lastrowid)

    def record_paper_fill(
        self,
        opportunity_id: str,
        venue: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into paper_fills (
                    created_at,
                    opportunity_id,
                    venue,
                    symbol,
                    side,
                    size,
                    price,
                    fee
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now().isoformat(),
                    opportunity_id,
                    venue,
                    symbol,
                    side,
                    str(size),
                    str(price),
                    str(fee),
                ),
            )
            return int(cursor.lastrowid)

    def fetch_all(self, sql: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql))
```

- [ ] **Step 4: Run ledger tests**

Run:

```bash
python -m pytest tests/unit/test_ledger.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/ledger.py tests/unit/test_ledger.py
git commit -m "feat: add sqlite ledger"
```

## Task 5: Fixture Market Data Loader

**Files:**
- Create: `data/fixtures/market_snapshots.json`
- Create: `src/stable_coin_trader/market_data.py`
- Create: `tests/unit/test_market_data.py`

- [ ] **Step 1: Write failing market data tests**

Create `tests/unit/test_market_data.py`:

```python
import json
from decimal import Decimal

from stable_coin_trader.market_data import load_market_snapshots


def test_load_market_snapshots_filters_symbol_and_venues(tmp_path) -> None:
    path = tmp_path / "market.json"
    path.write_text(
        json.dumps(
            [
                {
                    "venue": "coinbase",
                    "symbol": "USDC/USD",
                    "bid": "0.9999",
                    "ask": "1.0001",
                    "bid_size": "50000",
                    "ask_size": "50000",
                    "observed_at": "2026-05-13T12:00:00Z"
                },
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9995",
                    "ask": "0.9997",
                    "bid_size": "25000",
                    "ask_size": "25000",
                    "observed_at": "2026-05-13T12:00:00Z"
                },
                {
                    "venue": "gemini",
                    "symbol": "PYUSD/USD",
                    "bid": "0.9998",
                    "ask": "1.0000",
                    "bid_size": "10000",
                    "ask_size": "10000",
                    "observed_at": "2026-05-13T12:00:00Z"
                }
            ]
        )
    )

    snapshots = load_market_snapshots(path, symbols=["USDC/USD"], venues=["coinbase", "kraken"])

    assert len(snapshots) == 2
    assert snapshots[0].venue == "coinbase"
    assert snapshots[1].ask == Decimal("0.9997")
```

- [ ] **Step 2: Run market data tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_market_data.py -v
```

Expected: FAIL because `stable_coin_trader.market_data` does not exist.

- [ ] **Step 3: Implement fixture loader**

Create `src/stable_coin_trader/market_data.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from stable_coin_trader.models import MarketSnapshot


def load_market_snapshots(
    path: str | Path,
    symbols: list[str],
    venues: list[str],
) -> list[MarketSnapshot]:
    symbol_set = set(symbols)
    venue_set = set(venues)
    data = json.loads(Path(path).read_text())
    snapshots = [MarketSnapshot.model_validate(item) for item in data]
    return [
        snapshot
        for snapshot in snapshots
        if snapshot.symbol in symbol_set and snapshot.venue in venue_set
    ]
```

Create `data/fixtures/market_snapshots.json`:

```json
[
  {
    "venue": "coinbase",
    "symbol": "USDC/USD",
    "bid": "1.0000",
    "ask": "1.0002",
    "bid_size": "50000",
    "ask_size": "50000",
    "observed_at": "2026-05-13T12:00:00Z"
  },
  {
    "venue": "kraken",
    "symbol": "USDC/USD",
    "bid": "0.9994",
    "ask": "0.9996",
    "bid_size": "25000",
    "ask_size": "25000",
    "observed_at": "2026-05-13T12:00:00Z"
  }
]
```

- [ ] **Step 4: Run market data tests**

Run:

```bash
python -m pytest tests/unit/test_market_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/fixtures/market_snapshots.json src/stable_coin_trader/market_data.py tests/unit/test_market_data.py
git commit -m "feat: add fixture market data loader"
```

## Task 6: Research Signal Loader

**Files:**
- Create: `data/fixtures/research_signals.json`
- Create: `src/stable_coin_trader/research.py`
- Create: `tests/unit/test_research.py`

- [ ] **Step 1: Write failing research tests**

Create `tests/unit/test_research.py`:

```python
import json
from datetime import datetime, timezone

from stable_coin_trader.research import load_active_research_signals


def test_load_active_research_signals_filters_expired(tmp_path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "active",
                    "observed_at": "2026-05-13T12:00:00Z",
                    "published_at": "2026-05-13T11:59:00Z",
                    "source": "fixture",
                    "source_url": "https://example.com/active",
                    "source_quality": 0.8,
                    "affected_assets": ["USDC"],
                    "affected_venues": ["coinbase"],
                    "event_type": "venue_outage",
                    "direction": "risk_increase",
                    "severity": 3,
                    "confidence": 0.8,
                    "ttl_seconds": 3600,
                    "summary": "Active signal"
                },
                {
                    "id": "expired",
                    "observed_at": "2026-05-13T10:00:00Z",
                    "published_at": "2026-05-13T09:59:00Z",
                    "source": "fixture",
                    "source_url": "https://example.com/expired",
                    "source_quality": 0.8,
                    "affected_assets": ["USDC"],
                    "affected_venues": ["coinbase"],
                    "event_type": "venue_outage",
                    "direction": "risk_increase",
                    "severity": 3,
                    "confidence": 0.8,
                    "ttl_seconds": 60,
                    "summary": "Expired signal"
                }
            ]
        )
    )

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 12, 30, tzinfo=timezone.utc),
    )

    assert [signal.id for signal in active] == ["active"]
```

- [ ] **Step 2: Run research tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_research.py -v
```

Expected: FAIL because `stable_coin_trader.research` does not exist.

- [ ] **Step 3: Implement research signal loader**

Create `src/stable_coin_trader/research.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from stable_coin_trader.models import ResearchSignal


def load_active_research_signals(
    path: str | Path,
    now: datetime | None = None,
) -> list[ResearchSignal]:
    data = json.loads(Path(path).read_text())
    signals = [ResearchSignal.model_validate(item) for item in data]
    return [signal for signal in signals if not signal.is_expired(now)]
```

Create `data/fixtures/research_signals.json`:

```json
[
  {
    "id": "fixture-soft-warning",
    "observed_at": "2026-05-13T12:00:00Z",
    "published_at": "2026-05-13T11:58:00Z",
    "source": "fixture",
    "source_url": "https://example.com/stablecoin-risk",
    "source_quality": 0.7,
    "affected_assets": ["USDC"],
    "affected_venues": ["coinbase"],
    "event_type": "liquidity",
    "direction": "risk_increase",
    "severity": 2,
    "confidence": 0.8,
    "ttl_seconds": 86400,
    "summary": "Fixture signal that raises required edge for affected USDC trades."
  }
]
```

- [ ] **Step 4: Run research tests**

Run:

```bash
python -m pytest tests/unit/test_research.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/fixtures/research_signals.json src/stable_coin_trader/research.py tests/unit/test_research.py
git commit -m "feat: add fixture research signal loader"
```

## Task 7: Opportunity Engine

**Files:**
- Create: `src/stable_coin_trader/opportunities.py`
- Create: `tests/unit/test_opportunities.py`

- [ ] **Step 1: Write failing opportunity tests**

Create `tests/unit/test_opportunities.py`:

```python
from decimal import Decimal

from stable_coin_trader.models import MarketSnapshot
from stable_coin_trader.opportunities import find_spread_opportunities


def test_find_spread_opportunities_returns_profitable_cross_venue_trade() -> None:
    snapshots = [
        MarketSnapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid=Decimal("1.0000"),
            ask=Decimal("1.0002"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("50000"),
            observed_at="2026-05-13T12:00:00Z",
        ),
        MarketSnapshot(
            venue="kraken",
            symbol="USDC/USD",
            bid=Decimal("0.9994"),
            ask=Decimal("0.9996"),
            bid_size=Decimal("25000"),
            ask_size=Decimal("25000"),
            observed_at="2026-05-13T12:00:00Z",
        ),
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.buy_venue == "kraken"
    assert opportunity.sell_venue == "coinbase"
    assert opportunity.net_profit > 0


def test_find_spread_opportunities_ignores_same_venue() -> None:
    snapshots = [
        MarketSnapshot(
            venue="coinbase",
            symbol="USDC/USD",
            bid=Decimal("1.0000"),
            ask=Decimal("1.0002"),
            bid_size=Decimal("50000"),
            ask_size=Decimal("50000"),
            observed_at="2026-05-13T12:00:00Z",
        )
    ]

    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=Decimal("1000"),
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )

    assert opportunities == []
```

- [ ] **Step 2: Run opportunity tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_opportunities.py -v
```

Expected: FAIL because `stable_coin_trader.opportunities` does not exist.

- [ ] **Step 3: Implement opportunity engine**

Create `src/stable_coin_trader/opportunities.py`:

```python
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from stable_coin_trader.models import MarketSnapshot, Opportunity


def bps_cost(notional: Decimal, bps: Decimal) -> Decimal:
    return notional * bps / Decimal("10000")


def find_spread_opportunities(
    snapshots: list[MarketSnapshot],
    size: Decimal,
    fee_bps: Decimal,
    slippage_bps: Decimal,
) -> list[Opportunity]:
    by_symbol: dict[str, list[MarketSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_symbol[snapshot.symbol].append(snapshot)

    opportunities: list[Opportunity] = []
    for symbol, symbol_snapshots in by_symbol.items():
        for buy in symbol_snapshots:
            for sell in symbol_snapshots:
                if buy.venue == sell.venue:
                    continue
                executable_size = min(size, buy.ask_size, sell.bid_size)
                if executable_size <= 0:
                    continue
                notional = buy.ask * executable_size
                estimated_fees = bps_cost(notional, fee_bps * Decimal("2"))
                estimated_slippage = bps_cost(notional, slippage_bps)
                opportunity = Opportunity(
                    buy_venue=buy.venue,
                    sell_venue=sell.venue,
                    symbol=symbol,
                    size=executable_size,
                    buy_price=buy.ask,
                    sell_price=sell.bid,
                    estimated_fees=estimated_fees,
                    estimated_slippage=estimated_slippage,
                    observed_at=max(buy.observed_at, sell.observed_at),
                )
                if opportunity.net_profit > 0:
                    opportunities.append(opportunity)

    return sorted(opportunities, key=lambda item: item.net_profit, reverse=True)
```

- [ ] **Step 4: Run opportunity tests**

Run:

```bash
python -m pytest tests/unit/test_opportunities.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/opportunities.py tests/unit/test_opportunities.py
git commit -m "feat: add stablecoin opportunity engine"
```

## Task 8: Risk Engine

**Files:**
- Create: `src/stable_coin_trader/risk.py`
- Create: `tests/unit/test_risk.py`

- [ ] **Step 1: Write failing risk tests**

Create `tests/unit/test_risk.py`:

```python
from decimal import Decimal

from stable_coin_trader.config import BotConfig
from stable_coin_trader.models import Opportunity, ProposedTrade, ResearchSignal
from stable_coin_trader.risk import RiskEngine


def make_config() -> BotConfig:
    return BotConfig(
        mode="paper",
        ledger_path="paper.sqlite3",
        market_data_path="data/fixtures/market_snapshots.json",
        research_signals_path="data/fixtures/research_signals.json",
        base_currency="USD",
        symbols=["USDC/USD"],
        venues=["coinbase", "kraken"],
        max_order_usd="1000",
        max_position_usd="5000",
        min_edge_bps="2.5",
        stale_after_seconds=20,
        depeg_threshold_bps="30",
        daily_loss_limit_usd="25",
    )


def make_opportunity(net_edge_case: str = "profitable") -> Opportunity:
    sell_price = Decimal("1.0000") if net_edge_case == "profitable" else Decimal("0.9997")
    return Opportunity(
        buy_venue="kraken",
        sell_venue="coinbase",
        symbol="USDC/USD",
        size=Decimal("1000"),
        buy_price=Decimal("0.9995"),
        sell_price=sell_price,
        estimated_fees=Decimal("0.10"),
        estimated_slippage=Decimal("0.02"),
        observed_at="2026-05-13T12:00:00Z",
    )


def test_risk_engine_approves_trade_above_min_edge() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = ProposedTrade(
        opportunity_id=opportunity.id,
        side="buy",
        venue=opportunity.buy_venue,
        symbol=opportunity.symbol,
        size=opportunity.size,
        limit_price=opportunity.buy_price,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is True
    assert decision.reason == "approved"


def test_risk_engine_rejects_trade_below_min_edge() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity(net_edge_case="weak")
    trade = ProposedTrade(
        opportunity_id=opportunity.id,
        side="buy",
        venue=opportunity.buy_venue,
        symbol=opportunity.symbol,
        size=opportunity.size,
        limit_price=opportunity.buy_price,
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[])

    assert decision.approved is False
    assert decision.reason == "net edge below minimum"


def test_risk_engine_rejects_when_research_requires_review() -> None:
    engine = RiskEngine(make_config())
    opportunity = make_opportunity()
    trade = ProposedTrade(
        opportunity_id=opportunity.id,
        side="buy",
        venue=opportunity.buy_venue,
        symbol=opportunity.symbol,
        size=opportunity.size,
        limit_price=opportunity.buy_price,
    )
    signal = ResearchSignal(
        id="sig-1",
        observed_at="2026-05-13T12:00:00Z",
        published_at="2026-05-13T11:59:00Z",
        source="fixture",
        source_url="https://example.com/signal",
        source_quality=0.9,
        affected_assets=["USDC"],
        affected_venues=["kraken"],
        event_type="withdrawal_delay",
        direction="risk_increase",
        severity=5,
        confidence=0.9,
        ttl_seconds=3600,
        human_review_required=True,
        summary="High severity withdrawal delay.",
    )

    decision = engine.evaluate(trade=trade, opportunity=opportunity, signals=[signal])

    assert decision.approved is False
    assert decision.requires_human_approval is True
    assert decision.active_signal_ids == ["sig-1"]
```

- [ ] **Step 2: Run risk tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_risk.py -v
```

Expected: FAIL because `stable_coin_trader.risk` does not exist.

- [ ] **Step 3: Implement risk engine**

Create `src/stable_coin_trader/risk.py`:

```python
from __future__ import annotations

from decimal import Decimal

from stable_coin_trader.config import BotConfig
from stable_coin_trader.models import Opportunity, ProposedTrade, ResearchSignal, RiskDecision


class RiskEngine:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def evaluate(
        self,
        trade: ProposedTrade,
        opportunity: Opportunity,
        signals: list[ResearchSignal],
    ) -> RiskDecision:
        active_signals = self._signals_for_trade(trade, signals)
        active_signal_ids = [signal.id for signal in active_signals]

        if trade.size * trade.limit_price > self.config.max_order_usd:
            return RiskDecision.reject(
                trade=trade,
                reason="order exceeds max order size",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        if trade.size * trade.limit_price > self.config.max_position_usd:
            return RiskDecision.reject(
                trade=trade,
                reason="order exceeds max position size",
                min_edge_bps=self.config.min_edge_bps,
                active_signal_ids=active_signal_ids,
            )

        if any(signal.human_review_required for signal in active_signals):
            return RiskDecision.reject(
                trade=trade,
                reason="human review required by research signal",
                min_edge_bps=self.config.min_edge_bps,
                requires_human_approval=True,
                active_signal_ids=active_signal_ids,
            )

        min_edge = self._min_edge_with_signal_buffer(active_signals)
        if opportunity.net_edge_bps < min_edge:
            return RiskDecision.reject(
                trade=trade,
                reason="net edge below minimum",
                min_edge_bps=min_edge,
                active_signal_ids=active_signal_ids,
            )

        return RiskDecision.approve(
            trade=trade,
            reason="approved",
            min_edge_bps=min_edge,
            active_signal_ids=active_signal_ids,
        )

    def _signals_for_trade(
        self,
        trade: ProposedTrade,
        signals: list[ResearchSignal],
    ) -> list[ResearchSignal]:
        asset = trade.symbol.split("/")[0]
        return [
            signal
            for signal in signals
            if (
                asset in signal.affected_assets
                or trade.venue in signal.affected_venues
            )
            and signal.direction == "risk_increase"
        ]

    def _min_edge_with_signal_buffer(self, signals: list[ResearchSignal]) -> Decimal:
        buffer = sum((signal.risk_score for signal in signals), Decimal("0"))
        return self.config.min_edge_bps + buffer
```

- [ ] **Step 4: Run risk tests**

Run:

```bash
python -m pytest tests/unit/test_risk.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/risk.py tests/unit/test_risk.py
git commit -m "feat: add risk engine"
```

## Task 9: Paper Executor

**Files:**
- Create: `src/stable_coin_trader/paper.py`
- Create: `tests/unit/test_paper.py`

- [ ] **Step 1: Write failing paper executor tests**

Create `tests/unit/test_paper.py`:

```python
from decimal import Decimal

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import ProposedTrade, RiskDecision
from stable_coin_trader.paper import PaperExecutor


def test_paper_executor_records_fill_for_approved_trade(tmp_path) -> None:
    ledger = Ledger(tmp_path / "paper.sqlite3")
    ledger.initialize()
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
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
        reason="approved",
        min_edge_bps=Decimal("2.5"),
    )

    fill_id = executor.execute(decision)

    rows = ledger.fetch_all("select * from paper_fills")
    assert fill_id is not None
    assert len(rows) == 1
    assert rows[0]["opportunity_id"] == "opp-1"


def test_paper_executor_does_not_fill_rejected_trade(tmp_path) -> None:
    ledger = Ledger(tmp_path / "paper.sqlite3")
    ledger.initialize()
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))
    trade = ProposedTrade(
        opportunity_id="opp-1",
        side="buy",
        venue="kraken",
        symbol="USDC/USD",
        size=Decimal("1000"),
        limit_price=Decimal("0.9995"),
    )
    decision = RiskDecision.reject(trade=trade, reason="blocked")

    fill_id = executor.execute(decision)

    assert fill_id is None
    assert ledger.fetch_all("select * from paper_fills") == []
```

- [ ] **Step 2: Run paper executor tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_paper.py -v
```

Expected: FAIL because `stable_coin_trader.paper` does not exist.

- [ ] **Step 3: Implement paper executor**

Create `src/stable_coin_trader/paper.py`:

```python
from __future__ import annotations

from decimal import Decimal

from stable_coin_trader.ledger import Ledger
from stable_coin_trader.models import RiskDecision


class PaperExecutor:
    def __init__(self, ledger: Ledger, fee_bps: Decimal) -> None:
        self.ledger = ledger
        self.fee_bps = fee_bps

    def execute(self, decision: RiskDecision) -> int | None:
        self.ledger.record_risk_decision(decision)
        if not decision.approved:
            return None

        trade = decision.trade
        notional = trade.size * trade.limit_price
        fee = notional * self.fee_bps / Decimal("10000")
        return self.ledger.record_paper_fill(
            opportunity_id=trade.opportunity_id,
            venue=trade.venue,
            symbol=trade.symbol,
            side=trade.side,
            size=trade.size,
            price=trade.limit_price,
            fee=fee,
        )
```

- [ ] **Step 4: Run paper executor tests**

Run:

```bash
python -m pytest tests/unit/test_paper.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/paper.py tests/unit/test_paper.py
git commit -m "feat: add paper executor"
```

## Task 10: One-Cycle Engine Orchestration

**Files:**
- Create: `src/stable_coin_trader/engine.py`
- Create: `tests/integration/test_engine_cycle.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/integration/test_engine_cycle.py`:

```python
import json

from stable_coin_trader.config import BotConfig
from stable_coin_trader.engine import run_once
from stable_coin_trader.ledger import Ledger


def test_run_once_records_decision_and_fill(tmp_path) -> None:
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
                    "observed_at": "2026-05-13T12:00:00Z"
                },
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9994",
                    "ask": "0.9996",
                    "bid_size": "25000",
                    "ask_size": "25000",
                    "observed_at": "2026-05-13T12:00:00Z"
                }
            ]
        )
    )
    signals_path = tmp_path / "signals.json"
    signals_path.write_text("[]")
    ledger_path = tmp_path / "paper.sqlite3"
    config = BotConfig(
        mode="paper",
        ledger_path=str(ledger_path),
        market_data_path=str(market_path),
        research_signals_path=str(signals_path),
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

    result = run_once(config)

    ledger = Ledger(ledger_path)
    assert result.opportunities_seen == 1
    assert result.approved_trades == 2
    assert len(ledger.fetch_all("select * from risk_decisions")) == 2
    assert len(ledger.fetch_all("select * from paper_fills")) == 2
```

- [ ] **Step 2: Run integration test to verify it fails**

Run:

```bash
python -m pytest tests/integration/test_engine_cycle.py -v
```

Expected: FAIL because `stable_coin_trader.engine` does not exist.

- [ ] **Step 3: Implement one-cycle engine**

Create `src/stable_coin_trader/engine.py`:

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from stable_coin_trader.config import BotConfig
from stable_coin_trader.ledger import Ledger
from stable_coin_trader.market_data import load_market_snapshots
from stable_coin_trader.models import ProposedTrade
from stable_coin_trader.opportunities import find_spread_opportunities
from stable_coin_trader.paper import PaperExecutor
from stable_coin_trader.research import load_active_research_signals
from stable_coin_trader.risk import RiskEngine


class EngineRunResult(BaseModel):
    opportunities_seen: int
    approved_trades: int
    rejected_trades: int
    paper_fills: int


def run_once(config: BotConfig) -> EngineRunResult:
    ledger = Ledger(config.ledger_path)
    ledger.initialize()

    snapshots = load_market_snapshots(
        config.market_data_path,
        symbols=config.symbols,
        venues=config.venues,
    )
    signals = load_active_research_signals(config.research_signals_path)
    opportunities = find_spread_opportunities(
        snapshots=snapshots,
        size=config.max_order_usd,
        fee_bps=Decimal("1"),
        slippage_bps=Decimal("0.5"),
    )
    risk = RiskEngine(config)
    executor = PaperExecutor(ledger=ledger, fee_bps=Decimal("1"))

    approved = 0
    rejected = 0
    fills = 0

    for opportunity in opportunities:
        trades = [
            ProposedTrade(
                opportunity_id=opportunity.id,
                side="buy",
                venue=opportunity.buy_venue,
                symbol=opportunity.symbol,
                size=opportunity.size,
                limit_price=opportunity.buy_price,
            ),
            ProposedTrade(
                opportunity_id=opportunity.id,
                side="sell",
                venue=opportunity.sell_venue,
                symbol=opportunity.symbol,
                size=opportunity.size,
                limit_price=opportunity.sell_price,
            ),
        ]
        for trade in trades:
            decision = risk.evaluate(trade=trade, opportunity=opportunity, signals=signals)
            if decision.approved:
                approved += 1
            else:
                rejected += 1
            fill_id = executor.execute(decision)
            if fill_id is not None:
                fills += 1

    return EngineRunResult(
        opportunities_seen=len(opportunities),
        approved_trades=approved,
        rejected_trades=rejected,
        paper_fills=fills,
    )
```

- [ ] **Step 4: Run integration test**

Run:

```bash
python -m pytest tests/integration/test_engine_cycle.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/stable_coin_trader/engine.py tests/integration/test_engine_cycle.py
git commit -m "feat: add one cycle paper engine"
```

## Task 11: CLI Run Command

**Files:**
- Modify: `src/stable_coin_trader/cli.py`
- Create: `tests/integration/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

Create `tests/integration/test_cli.py`:

```python
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
                    "observed_at": "2026-05-13T12:00:00Z"
                },
                {
                    "venue": "kraken",
                    "symbol": "USDC/USD",
                    "bid": "0.9994",
                    "ask": "0.9996",
                    "bid_size": "25000",
                    "ask_size": "25000",
                    "observed_at": "2026-05-13T12:00:00Z"
                }
            ]
        )
    )
    signals_path = tmp_path / "signals.json"
    signals_path.write_text("[]")
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
                "stale_after_seconds": 20,
                "depeg_threshold_bps": "30",
                "daily_loss_limit_usd": "25"
            }
        )
    )

    result = CliRunner().invoke(app, ["run-once", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "opportunities=1" in result.output
    assert "approved=2" in result.output
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```bash
python -m pytest tests/integration/test_cli.py -v
```

Expected: FAIL because `run-once` is not registered.

- [ ] **Step 3: Add CLI command**

Replace `src/stable_coin_trader/cli.py` with:

```python
from pathlib import Path

import typer
from rich.console import Console

from stable_coin_trader.config import load_config
from stable_coin_trader.engine import run_once

app = typer.Typer(help="Risk-aware stablecoin paper trading bot.")
console = Console()


@app.callback()
def main() -> None:
    """Stable Coin Trader command line interface."""


@app.command("run-once")
def run_once_command(
    config: Path = typer.Option(..., "--config", help="Path to paper config JSON."),
) -> None:
    bot_config = load_config(config)
    result = run_once(bot_config)
    console.print(
        "paper run complete "
        f"opportunities={result.opportunities_seen} "
        f"approved={result.approved_trades} "
        f"rejected={result.rejected_trades} "
        f"fills={result.paper_fills}"
    )
```

- [ ] **Step 4: Run CLI test**

Run:

```bash
python -m pytest tests/integration/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/stable_coin_trader/cli.py tests/integration/test_cli.py
git commit -m "feat: add paper run cli"
```

## Task 12: Documentation and Project Tracking

**Files:**
- Modify: `README.md`
- Modify: `PROJECT.md`
- Modify: `PROJECT_LOG.md`

- [ ] **Step 1: Update README with local run instructions**

Replace `README.md` with:

````markdown
# Stable Coin Trader

Risk-aware stablecoin paper trading bot for proprietary capital.

Current phase: core skeleton and deterministic paper loop. The project does not contain live trading code yet.

Safety rules:

- No secrets in git.
- Paper mode first.
- Risk engine approves every proposed trade.
- Research signals can reduce risk, pause trading, or require review, but cannot originate trades.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -v
```

## Run One Paper Cycle

```bash
stable-coin-trader run-once --config config/paper.example.json
```

Expected output includes:

```text
paper run complete opportunities=1 approved=2 rejected=0 fills=2
```

The example config writes to `runtime/paper.sqlite3`, which is ignored by git.
````

- [ ] **Step 2: Update PROJECT.md current status**

In `PROJECT.md`, update Current Status to:

```markdown
Current phase: implementation plan approved or pending execution.

Completed:

- Researched stablecoin profit strategies.
- Researched relevant GitHub projects and frameworks.
- Confirmed the bot will trade only the owner's own capital.
- Selected Approach 2: Risk-Aware Stablecoin Trader.
- Connected this local folder to `trustlayersol/stable-coin-trader`.
- Created the initial design spec.
- Created the first implementation plan: `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.

Not started:

- No trading code has been implemented unless this plan has been executed.
- No API keys or secrets have been added.
- No live trading has been enabled.
- No exchange accounts have been connected.
```

- [ ] **Step 3: Update PROJECT_LOG.md**

Append to `PROJECT_LOG.md`:

```markdown

### Implementation Planning

- Created the first implementation plan at `docs/superpowers/plans/2026-05-13-core-skeleton-paper-loop.md`.
- Plan scope: Python bootstrap, config, models, SQLite ledger, fixture market data, fixture research signals, opportunity engine, risk engine, paper executor, one-cycle engine, and CLI.
- Deferred live trading, exchange API adapters, DEX execution, dashboard, and paid research sources to later plans.
```

- [ ] **Step 4: Run tests after documentation changes**

Run:

```bash
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md PROJECT.md PROJECT_LOG.md
git commit -m "docs: add paper loop usage notes"
```

## Verification

After all tasks are complete, run:

```bash
python -m pytest -v
stable-coin-trader run-once --config config/paper.example.json
git status --short
```

Expected:

- All tests pass.
- CLI prints `paper run complete opportunities=1 approved=2 rejected=0 fills=2`.
- Git status is clean.

## Handoff Notes

- This plan intentionally uses fixture data instead of real exchange APIs.
- This plan intentionally uses paper mode only.
- The next plan should add the first real market-data adapter, likely Coinbase or Kraken, without enabling live order placement.
- The risk engine remains the authority for all trade decisions.
- The research engine remains a defensive risk input only.
