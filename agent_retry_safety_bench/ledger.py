"""SQLite system of record for simulated maintenance tickets."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from agent_retry_safety_bench.models import (
    BenchmarkError,
    IncidentRequest,
    MaintenanceTicket,
    TicketDecision,
)


class SQLiteTicketLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    sequence INTEGER PRIMARY KEY,
                    equipment_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ticket_key ON tickets (idempotency_key)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> MaintenanceTicket:
        try:
            sequence = row[0]
            if not isinstance(sequence, int) or sequence < 1:
                raise BenchmarkError("TICKET_LEDGER_INVALID")
            return MaintenanceTicket(
                id=f"ticket-{1000 + sequence}",
                equipment_id=row[1],
                reason=row[2],
                idempotency_key=row[3],
            )
        except (BenchmarkError, TypeError, ValueError) as error:
            raise BenchmarkError("TICKET_LEDGER_INVALID") from error

    def create(
        self, request: IncidentRequest, decision: TicketDecision
    ) -> MaintenanceTicket:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets (equipment_id, reason, idempotency_key)
                VALUES (?, ?, ?)
                """,
                (request.equipment_id, decision.reason, request.idempotency_key),
            )
            sequence = cursor.lastrowid
        if sequence is None:
            raise BenchmarkError("TICKET_WRITE_FAILED")
        return MaintenanceTicket(
            id=f"ticket-{1000 + sequence}",
            equipment_id=request.equipment_id,
            reason=decision.reason,
            idempotency_key=request.idempotency_key,
        )

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> tuple[MaintenanceTicket, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, equipment_id, reason, idempotency_key
                FROM tickets
                WHERE idempotency_key = ?
                ORDER BY sequence
                """,
                (idempotency_key,),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def count(self, idempotency_key: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM tickets WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return int(row[0]) if row else 0
