"""Core contracts for the benchmark workflow."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class BenchmarkError(ValueError):
    """A benchmark failure with a stable machine-readable code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class WorkflowState(StrEnum):
    RECEIVED = "received"
    TELEMETRY_FETCHED = "telemetry_fetched"
    DECISION_MADE = "decision_made"
    TICKET_CREATED = "ticket_created"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class IncidentRequest:
    workflow_id: str
    equipment_id: str
    alarm_code: str
    idempotency_key: str

    def __post_init__(self) -> None:
        identifiers = (
            self.workflow_id,
            self.equipment_id,
            self.alarm_code,
            self.idempotency_key,
        )
        if any(not isinstance(identifier, str) or not identifier.strip() for identifier in identifiers):
            raise BenchmarkError("REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class Telemetry:
    equipment_id: str
    temperature_c: float
    alarms: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.equipment_id, str) or not self.equipment_id.strip():
            raise BenchmarkError("TELEMETRY_INVALID")
        if (
            isinstance(self.temperature_c, bool)
            or not isinstance(self.temperature_c, (int, float))
            or not math.isfinite(self.temperature_c)
        ):
            raise BenchmarkError("TELEMETRY_INVALID")
        if (
            not isinstance(self.alarms, tuple)
            or any(not isinstance(alarm, str) or not alarm.strip() for alarm in self.alarms)
            or len(self.alarms) != len(set(self.alarms))
        ):
            raise BenchmarkError("TELEMETRY_INVALID")


@dataclass(frozen=True, slots=True)
class TicketDecision:
    ticket_required: bool
    reason: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.ticket_required, bool)
            or not isinstance(self.reason, str)
            or not self.reason.strip()
        ):
            raise BenchmarkError("DECISION_INVALID")


@dataclass(frozen=True, slots=True)
class MaintenanceTicket:
    id: str
    equipment_id: str
    reason: str
    idempotency_key: str

    def __post_init__(self) -> None:
        values = (self.id, self.equipment_id, self.reason, self.idempotency_key)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise BenchmarkError("TICKET_INVALID")


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    workflow_id: str
    status: WorkflowState
    ticket_id: str
    recovery_strategy: str
    side_effect_count: int
    state_history: tuple[WorkflowState, ...]
    recovery_action: str = "none"
    attempts: int = 1
    retries: int = 0
    checkpoint_resumes: int = 0
    attempt_history: tuple[str, ...] = ("SUCCESS",)
