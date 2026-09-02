"""Explicit happy-path maintenance workflow."""

from __future__ import annotations

from failurebench.checkpoints import Checkpoint, SQLiteCheckpointStore
from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    WorkflowResult,
    WorkflowState,
)
from failurebench.tools import DeterministicTools


class MaintenanceWorkflow:
    def __init__(self, tools: DeterministicTools, checkpoints: SQLiteCheckpointStore):
        self.tools = tools
        self.checkpoints = checkpoints
        self.state = WorkflowState.RECEIVED
        self.state_history = [self.state]

    def _save(self, checkpoint: Checkpoint) -> None:
        self.checkpoints.save(checkpoint)
        self.state = checkpoint.state
        self.state_history.append(checkpoint.state)

    def run(self, request: IncidentRequest) -> WorkflowResult:
        checkpoint = self.checkpoints.load_latest(request.workflow_id)
        if checkpoint is None:
            checkpoint = Checkpoint(request, WorkflowState.RECEIVED)
            self.checkpoints.save(checkpoint)
        elif checkpoint.request != request:
            raise BenchmarkError("REQUEST_IDENTITY_MISMATCH")

        self.state = checkpoint.state
        self.state_history = list(self.checkpoints.history(request.workflow_id))
        telemetry = checkpoint.telemetry
        decision = checkpoint.decision
        ticket_id = checkpoint.ticket_id

        if self.state == WorkflowState.RECEIVED:
            telemetry = self.tools.read_telemetry(request.equipment_id)
            self._save(
                Checkpoint(request, WorkflowState.TELEMETRY_FETCHED, telemetry)
            )

        if self.state == WorkflowState.TELEMETRY_FETCHED:
            assert telemetry is not None
            decision = self.tools.decide_ticket(request, telemetry)
            self._save(
                Checkpoint(
                    request,
                    WorkflowState.DECISION_MADE,
                    telemetry,
                    decision,
                )
            )

        if self.state == WorkflowState.DECISION_MADE:
            assert telemetry is not None and decision is not None
            if not decision.ticket_required:
                raise BenchmarkError("ALARM_NOT_ACTIVE")
            ticket = self.tools.create_maintenance_ticket(request, decision)
            ticket_id = ticket.id
            self._save(
                Checkpoint(
                    request,
                    WorkflowState.TICKET_CREATED,
                    telemetry,
                    decision,
                    ticket_id,
                )
            )

        if self.state == WorkflowState.TICKET_CREATED:
            assert (
                telemetry is not None
                and decision is not None
                and ticket_id is not None
            )
            self._save(
                Checkpoint(
                    request,
                    WorkflowState.COMPLETED,
                    telemetry,
                    decision,
                    ticket_id,
                )
            )

        assert ticket_id is not None

        return WorkflowResult(
            workflow_id=request.workflow_id,
            status=self.state,
            ticket_id=ticket_id,
            recovery_strategy="baseline",
            side_effect_count=len(self.tools.tickets),
            state_history=tuple(self.state_history),
        )
