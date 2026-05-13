from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from stable_coin_trader.models import RiskDecision, decimal_key, parse_dt, utc_now


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
            self._ensure_risk_decisions_schema(conn)
            self._ensure_paper_fills_schema(conn)
            self._ensure_paper_fills_indexes(conn)
            self._ensure_foreign_keys_valid(conn)

    def record_risk_decision(
        self,
        decision: RiskDecision,
        created_at: datetime | None = None,
    ) -> int:
        with self.connect() as conn:
            return self._insert_risk_decision(conn, decision, created_at=created_at)

    def has_paper_fill_for_opportunity(self, opportunity_id: str) -> bool:
        with self.connect() as conn:
            return self._has_paper_fill_for_opportunity_ids(conn, [opportunity_id])

    def record_paper_fills_for_decisions(
        self,
        decisions: list[RiskDecision],
        fees: list[Decimal],
        created_at: datetime | None = None,
    ) -> list[int]:
        if len(decisions) != len(fees):
            raise ValueError("decisions and fees must have the same length")
        if not decisions:
            return []

        for decision, fee in zip(decisions, fees, strict=True):
            if not decision.approved:
                raise ValueError("paper fill decisions must be approved")
            self._validate_paper_fill_numbers(
                size=decision.trade.size,
                price=decision.trade.limit_price,
                fee=fee,
            )

        conn = self.connect()
        try:
            conn.execute("begin immediate")
            opportunity_ids = [decision.trade.opportunity_id for decision in decisions]
            if self._has_paper_fill_for_opportunity_ids(conn, opportunity_ids):
                conn.commit()
                return []

            fill_ids: list[int] = []
            for decision, fee in zip(decisions, fees, strict=True):
                risk_decision_id = self._insert_risk_decision(
                    conn,
                    decision,
                    created_at=created_at,
                )
                trade = decision.trade
                fill_ids.append(
                    self._insert_paper_fill(
                        conn=conn,
                        risk_decision_id=risk_decision_id,
                        opportunity_id=trade.opportunity_id,
                        venue=trade.venue,
                        symbol=trade.symbol,
                        side=trade.side,
                        size=trade.size,
                        price=trade.limit_price,
                        fee=fee,
                        created_at=created_at,
                    )
                )
            conn.commit()
            return fill_ids
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
        created_at: datetime | None = None,
    ) -> int:
        conn = self.connect()
        try:
            conn.execute("begin immediate")
            fill_id = self._insert_paper_fill(
                conn=conn,
                risk_decision_id=risk_decision_id,
                opportunity_id=opportunity_id,
                venue=venue,
                symbol=symbol,
                side=side,
                size=size,
                price=price,
                fee=fee,
                created_at=created_at,
            )
            conn.commit()
            return fill_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _validate_paper_fill_numbers(
        self,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
    ) -> None:
        self._require_positive_decimal("size", size)
        self._require_positive_decimal("price", price)
        self._require_nonnegative_decimal("fee", fee)

    def _require_positive_decimal(self, name: str, value: Decimal) -> None:
        if not value.is_finite() or value <= 0:
            raise ValueError(f"paper fill {name} must be positive and finite")

    def _require_nonnegative_decimal(self, name: str, value: Decimal) -> None:
        if not value.is_finite() or value < 0:
            raise ValueError(f"paper fill {name} must be nonnegative and finite")

    def _insert_risk_decision(
        self,
        conn: sqlite3.Connection,
        decision: RiskDecision,
        created_at: datetime | None = None,
    ) -> int:
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
                self._created_at_value(created_at),
                decision.trade.opportunity_id,
                decision.trade.venue,
                decision.trade.symbol,
                decision.trade.side,
                decimal_key(decision.trade.size),
                decimal_key(decision.trade.limit_price),
                1 if decision.approved else 0,
                decision.reason,
                decimal_key(decision.min_edge_bps),
                1 if decision.requires_human_approval else 0,
                json.dumps(decision.active_signal_ids),
            ),
        )
        return int(cursor.lastrowid)

    def _insert_paper_fill(
        self,
        conn: sqlite3.Connection,
        risk_decision_id: int,
        opportunity_id: str,
        venue: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
        created_at: datetime | None = None,
    ) -> int:
        self._validate_paper_fill_numbers(size=size, price=price, fee=fee)
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
                self._created_at_value(created_at),
                risk_decision_id,
                opportunity_id,
                venue,
                symbol,
                side,
                decimal_key(size),
                decimal_key(price),
                decimal_key(fee),
            ),
        )
        return int(cursor.lastrowid)

    def _created_at_value(self, created_at: datetime | None) -> str:
        return parse_dt(created_at or utc_now()).isoformat()

    def _has_paper_fill_for_opportunity_ids(
        self,
        conn: sqlite3.Connection,
        opportunity_ids: list[str],
    ) -> bool:
        unique_ids = sorted(set(opportunity_ids))
        if not unique_ids:
            return False

        placeholders = ", ".join("?" for _ in unique_ids)
        row = conn.execute(
            f"""
            select 1
            from paper_fills
            where opportunity_id in ({placeholders})
            limit 1
            """,
            unique_ids,
        ).fetchone()
        return row is not None

    def _ensure_risk_decisions_schema(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "risk_decisions"):
            self._create_risk_decisions_table(conn)
            return

        if self._risk_decisions_schema_is_valid(conn):
            return

        row_count = conn.execute("select count(*) from risk_decisions").fetchone()[0]
        if row_count:
            raise RuntimeError(
                "legacy risk_decisions schema contains rows; "
                "manual migration is required"
            )

        if self._table_exists(conn, "paper_fills"):
            fill_count = conn.execute("select count(*) from paper_fills").fetchone()[0]
            if fill_count:
                raise RuntimeError(
                    "legacy risk_decisions schema cannot be rebuilt while "
                    "paper_fills contains rows"
                )
            conn.execute("drop table paper_fills")

        conn.execute("drop table risk_decisions")
        self._create_risk_decisions_table(conn)

    def _ensure_paper_fills_schema(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "paper_fills"):
            self._create_paper_fills_table(conn)
            return

        if self._paper_fills_schema_is_valid(conn):
            return

        row_count = conn.execute("select count(*) from paper_fills").fetchone()[0]
        if row_count:
            raise RuntimeError(
                "legacy paper_fills schema contains rows without enforced "
                "risk decision links; manual migration is required"
            )

        conn.execute("drop table paper_fills")
        self._create_paper_fills_table(conn)

    def _ensure_paper_fills_indexes(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            create unique index if not exists idx_paper_fills_unique_leg
            on paper_fills (
                opportunity_id,
                side,
                venue,
                symbol,
                size,
                price
            )
            """
        )

    def _risk_decisions_schema_is_valid(self, conn: sqlite3.Connection) -> bool:
        expected_columns = {
            "id": ("integer", 0, 1),
            "created_at": ("text", 1, 0),
            "opportunity_id": ("text", 1, 0),
            "venue": ("text", 1, 0),
            "symbol": ("text", 1, 0),
            "side": ("text", 1, 0),
            "size": ("text", 1, 0),
            "limit_price": ("text", 1, 0),
            "approved": ("integer", 1, 0),
            "reason": ("text", 1, 0),
            "min_edge_bps": ("text", 1, 0),
            "requires_human_approval": ("integer", 1, 0),
            "active_signal_ids": ("text", 1, 0),
        }
        columns = {
            row["name"]: row
            for row in conn.execute("pragma table_info(risk_decisions)")
        }
        return self._columns_match(
            columns=columns,
            expected_columns=expected_columns,
        )

    def _paper_fills_schema_is_valid(self, conn: sqlite3.Connection) -> bool:
        expected_columns = {
            "id": ("integer", 0, 1),
            "created_at": ("text", 1, 0),
            "risk_decision_id": ("integer", 1, 0),
            "opportunity_id": ("text", 1, 0),
            "venue": ("text", 1, 0),
            "symbol": ("text", 1, 0),
            "side": ("text", 1, 0),
            "size": ("text", 1, 0),
            "price": ("text", 1, 0),
            "fee": ("text", 1, 0),
        }
        columns = {
            row["name"]: row for row in conn.execute("pragma table_info(paper_fills)")
        }
        if not self._columns_match(
            columns=columns,
            expected_columns=expected_columns,
        ):
            return False

        foreign_keys = list(conn.execute("pragma foreign_key_list(paper_fills)"))
        return any(
            row["from"] == "risk_decision_id"
            and row["table"] == "risk_decisions"
            and row["to"] == "id"
            for row in foreign_keys
        )

    def _columns_match(
        self,
        columns: dict[str, sqlite3.Row],
        expected_columns: dict[str, tuple[str, int, int]],
    ) -> bool:
        if set(columns) != set(expected_columns):
            return False

        for name, (expected_type, expected_notnull, expected_pk) in (
            expected_columns.items()
        ):
            column = columns[name]
            if column["type"].lower() != expected_type:
                return False
            if int(column["notnull"]) != expected_notnull:
                return False
            if int(column["pk"]) != expected_pk:
                return False
        return True

    def _ensure_foreign_keys_valid(self, conn: sqlite3.Connection) -> None:
        violations = list(conn.execute("pragma foreign_key_check"))
        if violations:
            raise RuntimeError("ledger contains foreign key violations")

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            """
            select 1
            from sqlite_master
            where type = 'table' and name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def _create_risk_decisions_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
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
            )
            """
        )

    def _create_paper_fills_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
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
            )
            """
        )

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
                limit_price,
                approved
            from risk_decisions
            where id = ?
            """,
            (risk_decision_id,),
        ).fetchone()
        if row is None:
            return
        if row["approved"] != 1:
            raise ValueError(f"risk decision {risk_decision_id} is not approved")

        expected = {
            "opportunity_id": row["opportunity_id"],
            "venue": row["venue"],
            "symbol": row["symbol"],
            "side": row["side"],
        }
        actual = {
            "opportunity_id": opportunity_id,
            "venue": venue,
            "symbol": symbol,
            "side": side,
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

        decision_size = Decimal(row["size"])
        limit_price = Decimal(row["limit_price"])
        existing_filled_size = sum(
            (
                Decimal(fill["size"])
                for fill in conn.execute(
                    "select size from paper_fills where risk_decision_id = ?",
                    (risk_decision_id,),
                )
            ),
            Decimal("0"),
        )
        if existing_filled_size + size > decision_size:
            raise ValueError(
                "paper fill size exceeds approved risk decision size "
                f"{decision_size}"
            )

        if side == "buy" and price > limit_price:
            raise ValueError(
                "paper fill price exceeds approved buy limit "
                f"{limit_price}"
            )
        if side == "sell" and price < limit_price:
            raise ValueError(
                "paper fill price is below approved sell limit "
                f"{limit_price}"
            )

    def fetch_all(self, sql: str) -> list[sqlite3.Row]:
        if not self._is_read_only_sql(sql):
            raise ValueError("fetch_all is read-only")
        with self.connect() as conn:
            return list(conn.execute(sql))

    def _is_read_only_sql(self, sql: str) -> bool:
        statement = sql.strip()
        if statement.endswith(";"):
            statement = statement[:-1].strip()
        if not statement or ";" in statement:
            return False

        lowered = statement.lower()
        if lowered.startswith("select "):
            return True
        if lowered == "pragma user_version":
            return True
        return lowered.startswith("pragma table_info(") or lowered.startswith(
            "pragma foreign_key_list("
        )
