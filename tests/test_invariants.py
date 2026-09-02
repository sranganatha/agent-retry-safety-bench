import unittest
from dataclasses import replace

from agent_retry_safety_bench.invariants import InvariantEvidence, evaluate_invariants
from agent_retry_safety_bench.models import IncidentRequest, WorkflowState


class InvariantTest(unittest.TestCase):
    def setUp(self) -> None:
        self.request = IncidentRequest(
            "wf-123", "etch-101", "TEMP_HIGH", "wf-123:create-ticket"
        )
        self.valid = InvariantEvidence(
            status="completed",
            ticket_id="ticket-1001",
            attempts=1,
            max_attempts=1,
            error_code=None,
            state_history=tuple(WorkflowState),
            ticket_ids=("ticket-1001",),
            request=self.request,
            checkpoint_request=self.request,
        )

    def assert_only_fails(self, name: str, evidence: InvariantEvidence) -> None:
        results = evaluate_invariants(evidence)
        self.assertFalse(results.pop(name))
        self.assertTrue(all(results.values()))

    def test_maximum_one_ticket(self) -> None:
        self.assert_only_fails(
            "maximum_one_ticket",
            replace(self.valid, ticket_ids=("ticket-1001", "ticket-1002")),
        )

    def test_retry_budget_respected(self) -> None:
        self.assert_only_fails(
            "retry_budget_respected",
            replace(self.valid, attempts=2),
        )

    def test_checkpoint_monotonic(self) -> None:
        self.assert_only_fails(
            "checkpoint_monotonic",
            replace(
                self.valid,
                state_history=(WorkflowState.RECEIVED, WorkflowState.DECISION_MADE),
            ),
        )

    def test_no_completion_on_invalid_output(self) -> None:
        self.assert_only_fails(
            "no_completion_on_invalid_output",
            replace(self.valid, error_code="DECISION_INVALID"),
        )

    def test_result_matches_ledger(self) -> None:
        self.assert_only_fails(
            "result_matches_ledger",
            replace(self.valid, ticket_ids=()),
        )

    def test_same_request_identity(self) -> None:
        changed = IncidentRequest(
            "wf-123", "etch-101", "PRESSURE_HIGH", "wf-123:create-ticket"
        )
        self.assert_only_fails(
            "same_request_identity",
            replace(self.valid, checkpoint_request=changed),
        )


if __name__ == "__main__":
    unittest.main()
