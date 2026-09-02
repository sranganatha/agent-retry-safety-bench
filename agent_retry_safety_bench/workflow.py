"""Explicit happy-path maintenance workflow."""

from __future__ import annotations

from agent_retry_safety_bench.checkpoints import Checkpoint, SQLiteCheckpointStore
from agent_retry_safety_bench.models import (
    BenchmarkError,
    IncidentRequest,
    WorkflowResult,
    WorkflowState,
)
from agent_retry_safety_bench.tools import DeterministicTools


class MaintenanceWorkflow:
    def __init__(self, tools: DeterministicTools, checkpoints: SQLiteCheckpointStore):
        if tools.ticket_ledger.path.resolve() == checkpoints.path.resolve():
            raise BenchmarkError("STORAGE_BOUNDARY_INVALID")
        self.tools = tools
        self.checkpoints = checkpoints
        self.state = WorkflowState.RECEIVED
        self.state_history: list[WorkflowState] = []

    def _save(self, checkpoint: Checkpoint) -> None:
        self.tools.faults.before_checkpoint()
        self.checkpoints.save(checkpoint)
        self.tools.faults.after_checkpoint()
        self.state = checkpoint.state
        self.state_history.append(checkpoint.state)

    def run(self, request: IncidentRequest) -> WorkflowResult:
        checkpoint = self.checkpoints.load_latest(request.workflow_id)
        if checkpoint is None:
            checkpoint = Checkpoint(request, WorkflowState.RECEIVED)
            self._save(checkpoint)
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
            side_effect_count=self.tools.ticket_count(request.idempotency_key),
            state_history=tuple(self.state_history),
        )
