from __future__ import annotations

import json
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
        conn.execute("pragma foreign_keys = on")
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
                    risk_decision_id integer not null references risk_decisions(id),
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
                    json.dumps(decision.active_signal_ids),
                ),
            )
            return int(cursor.lastrowid)

    def record_paper_fill(
        self,
        risk_decision_id: int,
        opportunity_id: str,
        venue: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
    ) -> int:
        with self.connect() as conn:
            self._validate_paper_fill_matches_decision(
                conn=conn,
                risk_decision_id=risk_decision_id,
                opportunity_id=opportunity_id,
                venue=venue,
                symbol=symbol,
                side=side,
                size=size,
                price=price,
            )
            cursor = conn.execute(
                """
                insert into paper_fills (
                    created_at,
                    risk_decision_id,
                    opportunity_id,
                    venue,
                    symbol,
                    side,
                    size,
                    price,
                    fee
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now().isoformat(),
                    risk_decision_id,
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

    def _validate_paper_fill_matches_decision(
        self,
        conn: sqlite3.Connection,
        risk_decision_id: int,
        opportunity_id: str,
        venue: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
    ) -> None:
        row = conn.execute(
            """
            select
                opportunity_id,
                venue,
                symbol,
                side,
                size,
                limit_price
            from risk_decisions
            where id = ?
            """,
            (risk_decision_id,),
        ).fetchone()
        if row is None:
            return

        expected = {
            "opportunity_id": row["opportunity_id"],
            "venue": row["venue"],
            "symbol": row["symbol"],
            "side": row["side"],
            "size": row["size"],
            "price": row["limit_price"],
        }
        actual = {
            "opportunity_id": opportunity_id,
            "venue": venue,
            "symbol": symbol,
            "side": side,
            "size": str(size),
            "price": str(price),
        }
        mismatches = [
            field
            for field, expected_value in expected.items()
            if actual[field] != expected_value
        ]
        if mismatches:
            details = ", ".join(
                f"{field} expected {expected[field]!r} got {actual[field]!r}"
                for field in mismatches
            )
            raise ValueError(
                "paper fill does not match risk decision "
                f"{risk_decision_id}: {details}"
            )

    def fetch_all(self, sql: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql))
