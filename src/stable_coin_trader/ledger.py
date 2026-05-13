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
