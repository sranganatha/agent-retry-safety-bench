"""Deterministic telemetry, decision, and maintenance tool fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field

from failurebench.config import BenchmarkConfig
from failurebench.faults import FaultInjector
from failurebench.ledger import SQLiteTicketLedger
from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    MaintenanceTicket,
    Telemetry,
    TicketDecision,
)
from failurebench.scenarios import FailureKind


@dataclass(slots=True)
class DeterministicTools:
    config: BenchmarkConfig
    ticket_ledger: SQLiteTicketLedger
    faults: FaultInjector = field(default_factory=FaultInjector)

    def read_telemetry(self, equipment_id: str) -> Telemetry:
        self.faults.before_call("read_telemetry")
        equipment = next(
            (item for item in self.config.equipment if item.id == equipment_id), None
        )
        if equipment is None:
            raise BenchmarkError("EQUIPMENT_NOT_FOUND")
        return Telemetry(equipment.id, equipment.temperature_c, equipment.alarms)

    def decide_ticket(
        self, request: IncidentRequest, telemetry: Telemetry
    ) -> TicketDecision:
        injected = self.faults.before_call("decide_ticket")
        if injected == FailureKind.MALFORMED_OUTPUT:
            return TicketDecision(ticket_required="yes", reason="")
        is_active = request.alarm_code in telemetry.alarms
        return TicketDecision(
            ticket_required=is_active,
            reason=f"Investigate {request.alarm_code} on {request.equipment_id}",
        )

    def create_maintenance_ticket(
        self, request: IncidentRequest, decision: TicketDecision
    ) -> MaintenanceTicket:
        self.faults.before_call("create_ticket")
        ticket = self.ticket_ledger.create(request, decision)
        self.faults.after_side_effect("create_ticket")
        return ticket

    def find_maintenance_tickets(
        self, idempotency_key: str
    ) -> tuple[MaintenanceTicket, ...]:
        return self.ticket_ledger.find_by_idempotency_key(idempotency_key)

    def ticket_count(self, idempotency_key: str) -> int:
        return self.ticket_ledger.count(idempotency_key)
