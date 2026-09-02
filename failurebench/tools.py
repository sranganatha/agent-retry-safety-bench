"""Deterministic telemetry, decision, and maintenance tool fixtures."""

from __future__ import annotations

from dataclasses import dataclass

from failurebench.config import BenchmarkConfig
from failurebench.ledger import SQLiteTicketLedger
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
    ticket_ledger: SQLiteTicketLedger

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
        return self.ticket_ledger.create(request, decision)

    def find_maintenance_tickets(
        self, idempotency_key: str
    ) -> tuple[MaintenanceTicket, ...]:
        return self.ticket_ledger.find_by_idempotency_key(idempotency_key)

    def ticket_count(self, idempotency_key: str) -> int:
        return self.ticket_ledger.count(idempotency_key)
