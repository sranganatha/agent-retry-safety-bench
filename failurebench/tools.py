"""Deterministic telemetry, decision, and maintenance tool fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field

from failurebench.config import BenchmarkConfig
from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    MaintenanceTicket,
    Telemetry,
    TicketDecision,
)


@dataclass(slots=True)
class DeterministicTools:
    config: BenchmarkConfig
    tickets: list[MaintenanceTicket] = field(default_factory=list)

    def read_telemetry(self, equipment_id: str) -> Telemetry:
        equipment = next(
            (item for item in self.config.equipment if item.id == equipment_id), None
        )
        if equipment is None:
            raise BenchmarkError("EQUIPMENT_NOT_FOUND")
        return Telemetry(equipment.id, equipment.temperature_c, equipment.alarms)

    def decide_ticket(
        self, request: IncidentRequest, telemetry: Telemetry
    ) -> TicketDecision:
        is_active = request.alarm_code in telemetry.alarms
        return TicketDecision(
            ticket_required=is_active,
            reason=f"Investigate {request.alarm_code} on {request.equipment_id}",
        )

    def create_maintenance_ticket(
        self, request: IncidentRequest, decision: TicketDecision
    ) -> MaintenanceTicket:
        ticket = MaintenanceTicket(
            id=f"ticket-{1001 + len(self.tickets)}",
            equipment_id=request.equipment_id,
            reason=decision.reason,
            idempotency_key=request.idempotency_key,
        )
        self.tickets.append(ticket)
        return ticket
