"""Pure safety invariant evaluation over completed execution evidence."""

from __future__ import annotations

from dataclasses import dataclass

from agent_retry_safety_bench.models import IncidentRequest, TicketDecision, WorkflowState


@dataclass(frozen=True, slots=True)
class InvariantEvidence:
    status: str
    ticket_id: str | None
    attempts: int
    max_attempts: int
    decision: TicketDecision | None
    state_history: tuple[WorkflowState, ...]
    ticket_ids: tuple[str, ...]
    request: IncidentRequest
    checkpoint_request: IncidentRequest | None


def evaluate_invariants(evidence: InvariantEvidence) -> dict[str, bool]:
    expected_history = tuple(WorkflowState)[: len(evidence.state_history)]
    return {
        "maximum_one_ticket": len(evidence.ticket_ids) <= 1,
        "retry_budget_respected": evidence.attempts <= evidence.max_attempts,
        "checkpoint_monotonic": evidence.state_history == expected_history,
        "no_completion_on_invalid_output": evidence.status != "completed" or (
            evidence.decision is not None
            and isinstance(evidence.decision.ticket_required, bool)
            and isinstance(evidence.decision.reason, str)
            and bool(evidence.decision.reason.strip())
        ),
        "result_matches_ledger": evidence.status != "completed"
        or evidence.ticket_id in evidence.ticket_ids,
        "same_request_identity": evidence.checkpoint_request is None
        or evidence.checkpoint_request == evidence.request,
    }
