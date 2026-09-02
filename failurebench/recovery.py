"""Bounded recovery strategies for deterministic workflow failures."""

from __future__ import annotations

from dataclasses import replace

from failurebench.checkpoints import Checkpoint, SQLiteCheckpointStore
from failurebench.faults import FaultInjector, InjectedFailure
from failurebench.models import BenchmarkError, WorkflowResult, WorkflowState
from failurebench.scenarios import (
    FailureKind,
    LifecyclePoint,
    RecoveryAction,
    RecoveryStrategy,
    Scenario,
)
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


class RecoveryFailure(BenchmarkError):
    def __init__(
        self,
        code: str,
        cause_code: str,
        strategy: RecoveryStrategy,
        action: RecoveryAction,
        attempt_history: tuple[str, ...],
        checkpoint_resumes: int,
    ):
        super().__init__(code)
        self.cause_code = cause_code
        self.strategy = strategy
        self.action = action
        self.attempt_history = attempt_history
        self.attempts = len(attempt_history)
        self.retries = max(0, self.attempts - 1)
        self.checkpoint_resumes = checkpoint_resumes


def _failure(
    code: str,
    cause_code: str,
    scenario: Scenario,
    action: RecoveryAction,
    attempt_history: list[str],
    checkpoint_resumes: int,
) -> RecoveryFailure:
    return RecoveryFailure(
        code,
        cause_code,
        scenario.recovery_strategy,
        action,
        tuple(attempt_history),
        checkpoint_resumes,
    )


def _reconcile_ticket(
    scenario: Scenario,
    tools: DeterministicTools,
    checkpoints: SQLiteCheckpointStore,
) -> bool:
    tickets = tools.find_maintenance_tickets(scenario.request.idempotency_key)
    if not tickets:
        return False
    if len(tickets) != 1:
        raise BenchmarkError("RECONCILIATION_AMBIGUOUS")

    latest = checkpoints.load_latest(scenario.request.workflow_id)
    if (
        latest is None
        or latest.state != WorkflowState.DECISION_MADE
        or latest.telemetry is None
        or latest.decision is None
    ):
        raise BenchmarkError("RECONCILIATION_STATE_INVALID")
    ticket = tickets[0]
    if (
        ticket.equipment_id != scenario.request.equipment_id
        or ticket.reason != latest.decision.reason
    ):
        raise BenchmarkError("RECONCILIATION_MISMATCH")

    checkpoints.save(
        Checkpoint(
            scenario.request,
            WorkflowState.TICKET_CREATED,
            latest.telemetry,
            latest.decision,
            ticket.id,
        )
    )
    return True


def run_with_recovery(
    scenario: Scenario,
    tools: DeterministicTools,
    checkpoints: SQLiteCheckpointStore,
) -> WorkflowResult:
    tools.faults = FaultInjector(scenario.injection)
    attempt_history: list[str] = []
    checkpoint_resumes = 0
    action = RecoveryAction.NONE

    for attempt in range(1, scenario.max_attempts + 1):
        if attempt > 1 and checkpoints.load_latest(scenario.request.workflow_id):
            checkpoint_resumes += 1
        try:
            result = MaintenanceWorkflow(tools, checkpoints).run(scenario.request)
        except InjectedFailure as error:
            attempt_history.append(error.code)
            if scenario.recovery_strategy == RecoveryStrategy.BASELINE:
                raise _failure(
                    error.code,
                    error.code,
                    scenario,
                    RecoveryAction.FAIL,
                    attempt_history,
                    checkpoint_resumes,
                ) from error
            if attempt == scenario.max_attempts:
                raise _failure(
                    "RETRY_BUDGET_EXHAUSTED",
                    error.code,
                    scenario,
                    RecoveryAction.FAIL,
                    attempt_history,
                    checkpoint_resumes,
                ) from error

            injection = error.injection
            if injection.failure == FailureKind.PROCESS_INTERRUPTION:
                action = RecoveryAction.RESUME
            elif (
                scenario.recovery_strategy == RecoveryStrategy.RECONCILE_THEN_RETRY
                and injection.operation == "create_ticket"
                and injection.lifecycle_point == LifecyclePoint.AFTER_SIDE_EFFECT
            ):
                action = RecoveryAction.RECONCILE
                try:
                    if not _reconcile_ticket(scenario, tools, checkpoints):
                        action = RecoveryAction.RETRY
                except BenchmarkError as reconciliation_error:
                    raise _failure(
                        reconciliation_error.code,
                        reconciliation_error.code,
                        scenario,
                        RecoveryAction.FAIL,
                        attempt_history,
                        checkpoint_resumes,
                    ) from reconciliation_error
            else:
                action = RecoveryAction.RETRY
            continue
        except BenchmarkError as error:
            attempt_history.append(error.code)
            raise _failure(
                error.code,
                error.code,
                scenario,
                RecoveryAction.FAIL,
                attempt_history,
                checkpoint_resumes,
            ) from error

        attempt_history.append("SUCCESS")
        return replace(
            result,
            recovery_strategy=scenario.recovery_strategy,
            recovery_action=action,
            attempts=len(attempt_history),
            retries=len(attempt_history) - 1,
            checkpoint_resumes=checkpoint_resumes,
            attempt_history=tuple(attempt_history),
        )

    raise AssertionError("bounded recovery loop exited unexpectedly")
