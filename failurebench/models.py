"""Core contracts for the benchmark workflow."""

from __future__ import annotations

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


@dataclass(frozen=True, slots=True)
class TicketDecision:
    ticket_required: bool
    reason: str


@dataclass(frozen=True, slots=True)
class MaintenanceTicket:
    id: str
    equipment_id: str
    reason: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    workflow_id: str
    status: WorkflowState
    ticket_id: str
    recovery_strategy: str
    side_effect_count: int
    state_history: tuple[WorkflowState, ...]
