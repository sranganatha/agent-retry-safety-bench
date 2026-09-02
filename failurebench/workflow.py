"""Explicit happy-path maintenance workflow."""

from __future__ import annotations

from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    WorkflowResult,
    WorkflowState,
)
from failurebench.tools import DeterministicTools


class MaintenanceWorkflow:
    def __init__(self, tools: DeterministicTools):
        self.tools = tools
        self.state = WorkflowState.RECEIVED
        self.state_history = [self.state]

    def _advance(self, state: WorkflowState) -> None:
        self.state = state
        self.state_history.append(state)

    def run(self, request: IncidentRequest) -> WorkflowResult:
        if self.state != WorkflowState.RECEIVED or len(self.state_history) != 1:
            raise BenchmarkError("WORKFLOW_ALREADY_RUN")

        telemetry = self.tools.read_telemetry(request.equipment_id)
        self._advance(WorkflowState.TELEMETRY_FETCHED)

        decision = self.tools.decide_ticket(request, telemetry)
        self._advance(WorkflowState.DECISION_MADE)
        if not decision.ticket_required:
            raise BenchmarkError("ALARM_NOT_ACTIVE")

        ticket = self.tools.create_maintenance_ticket(request, decision)
        self._advance(WorkflowState.TICKET_CREATED)
        self._advance(WorkflowState.COMPLETED)

        return WorkflowResult(
            workflow_id=request.workflow_id,
            status=self.state,
            ticket_id=ticket.id,
            recovery_strategy="baseline",
            side_effect_count=len(self.tools.tickets),
            state_history=tuple(self.state_history),
        )
