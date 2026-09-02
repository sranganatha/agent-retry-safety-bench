"""SQLite checkpoints for deterministic workflow resume."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    Telemetry,
    TicketDecision,
    WorkflowState,
)


STATE_ORDER = {state: position for position, state in enumerate(WorkflowState)}


@dataclass(frozen=True, slots=True)
class Checkpoint:
    request: IncidentRequest
    state: WorkflowState
    telemetry: Telemetry | None = None
    decision: TicketDecision | None = None
    ticket_id: str | None = None

    def __post_init__(self) -> None:
        position = STATE_ORDER[self.state]
        expected = (
            position >= STATE_ORDER[WorkflowState.TELEMETRY_FETCHED],
            position >= STATE_ORDER[WorkflowState.DECISION_MADE],
            position >= STATE_ORDER[WorkflowState.TICKET_CREATED],
        )
        actual = (
            self.telemetry is not None,
            self.decision is not None,
            self.ticket_id is not None,
        )
        if actual != expected:
            raise BenchmarkError("CHECKPOINT_INVALID")
        if self.telemetry and self.telemetry.equipment_id != self.request.equipment_id:
            raise BenchmarkError("CHECKPOINT_INVALID")
        if (
            position >= STATE_ORDER[WorkflowState.TICKET_CREATED]
            and self.decision
            and not self.decision.ticket_required
        ):
            raise BenchmarkError("CHECKPOINT_INVALID")
        if self.ticket_id is not None and (
            not isinstance(self.ticket_id, str) or not self.ticket_id.strip()
        ):
            raise BenchmarkError("CHECKPOINT_INVALID")


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    workflow_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    equipment_id TEXT NOT NULL,
                    alarm_code TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    telemetry_json TEXT,
                    decision_json TEXT,
                    ticket_id TEXT,
                    PRIMARY KEY (workflow_id, sequence),
                    UNIQUE (workflow_id, state)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> Checkpoint:
        try:
            request = IncidentRequest(row[0], row[3], row[4], row[5])
            state = WorkflowState(row[2])
            if row[1] != STATE_ORDER[state]:
                raise BenchmarkError("CHECKPOINT_INVALID")
            telemetry_raw = json.loads(str(row[6])) if row[6] is not None else None
            decision_raw = json.loads(str(row[7])) if row[7] is not None else None
            telemetry = (
                Telemetry(
                    equipment_id=telemetry_raw["equipment_id"],
                    temperature_c=telemetry_raw["temperature_c"],
                    alarms=tuple(telemetry_raw["alarms"]),
                )
                if telemetry_raw is not None
                else None
            )
            decision = TicketDecision(**decision_raw) if decision_raw is not None else None
            return Checkpoint(request, state, telemetry, decision, row[8])
        except (BenchmarkError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise BenchmarkError("CHECKPOINT_INVALID") from error

    def _latest(
        self, connection: sqlite3.Connection, workflow_id: str
    ) -> Checkpoint | None:
        row = connection.execute(
            """
            SELECT workflow_id, sequence, state, equipment_id, alarm_code,
                   idempotency_key, telemetry_json, decision_json, ticket_id
            FROM checkpoints
            WHERE workflow_id = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def load_latest(self, workflow_id: str) -> Checkpoint | None:
        with self._connect() as connection:
            return self._latest(connection, workflow_id)

    def history(self, workflow_id: str) -> tuple[WorkflowState, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, state
                FROM checkpoints
                WHERE workflow_id = ?
                ORDER BY sequence
                """,
                (workflow_id,),
            ).fetchall()
        try:
            states = tuple(WorkflowState(row[1]) for row in rows)
            if any(row[0] != STATE_ORDER[state] for row, state in zip(rows, states)):
                raise BenchmarkError("CHECKPOINT_INVALID")
            if states != tuple(WorkflowState)[: len(states)]:
                raise BenchmarkError("CHECKPOINT_INVALID")
            return states
        except (TypeError, ValueError) as error:
            raise BenchmarkError("CHECKPOINT_INVALID") from error

    def save(self, checkpoint: Checkpoint) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = self._latest(connection, checkpoint.request.workflow_id)
            position = STATE_ORDER[checkpoint.state]
            if latest is None:
                valid_transition = checkpoint.state == WorkflowState.RECEIVED
            else:
                valid_transition = position == STATE_ORDER[latest.state] + 1
                if latest.request != checkpoint.request:
                    raise BenchmarkError("REQUEST_IDENTITY_MISMATCH")
            if not valid_transition:
                raise BenchmarkError("CHECKPOINT_NON_MONOTONIC")

            connection.execute(
                """
                INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.request.workflow_id,
                    position,
                    checkpoint.state,
                    checkpoint.request.equipment_id,
                    checkpoint.request.alarm_code,
                    checkpoint.request.idempotency_key,
                    json.dumps(asdict(checkpoint.telemetry), sort_keys=True)
                    if checkpoint.telemetry
                    else None,
                    json.dumps(asdict(checkpoint.decision), sort_keys=True)
                    if checkpoint.decision
                    else None,
                    checkpoint.ticket_id,
                ),
            )
