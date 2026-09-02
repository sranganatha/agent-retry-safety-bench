import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_retry_safety_bench.checkpoints import SQLiteCheckpointStore
from agent_retry_safety_bench.config import load_config
from agent_retry_safety_bench.ledger import SQLiteTicketLedger
from agent_retry_safety_bench.recovery import RecoveryFailure, run_with_recovery
from agent_retry_safety_bench.scenarios import (
    FailureKind,
    Injection,
    LifecyclePoint,
    RecoveryAction,
    RecoveryStrategy,
    load_scenario,
)
from agent_retry_safety_bench.tools import DeterministicTools


class RecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.checkpoints = SQLiteCheckpointStore(root / "checkpoints.db")
        self.ledger = SQLiteTicketLedger(root / "tickets.db")
        self.tools = DeterministicTools(load_config("config/demo.json"), self.ledger)
        self.timeout_after_ticket = load_scenario(
            "scenarios/timeout-after-ticket.yaml"
        )

    def run_scenario(self, scenario):
        return run_with_recovery(scenario, self.tools, self.checkpoints)

    def test_baseline_completes_without_recovery(self) -> None:
        result = self.run_scenario(load_scenario("scenarios/baseline.yaml"))

        self.assertEqual(RecoveryAction.NONE, result.recovery_action)
        self.assertEqual(1, result.attempts)
        self.assertEqual(0, result.retries)
        self.assertEqual(("SUCCESS",), result.attempt_history)

    def test_naive_retry_duplicates_an_uncertain_ticket_write(self) -> None:
        result = self.run_scenario(self.timeout_after_ticket)

        self.assertEqual("ticket-1002", result.ticket_id)
        self.assertEqual(2, result.side_effect_count)
        self.assertEqual(RecoveryAction.RETRY, result.recovery_action)
        self.assertEqual(2, result.attempts)
        self.assertEqual(1, result.retries)
        self.assertEqual(1, result.checkpoint_resumes)
        self.assertEqual(("INJECTED_TIMEOUT", "SUCCESS"), result.attempt_history)

    def test_reconciliation_reuses_the_uncertain_ticket_write(self) -> None:
        scenario = replace(
            self.timeout_after_ticket,
            recovery_strategy=RecoveryStrategy.RECONCILE_THEN_RETRY,
        )

        result = self.run_scenario(scenario)

        self.assertEqual("ticket-1001", result.ticket_id)
        self.assertEqual(1, result.side_effect_count)
        self.assertEqual(RecoveryAction.RECONCILE, result.recovery_action)
        self.assertEqual(("INJECTED_TIMEOUT", "SUCCESS"), result.attempt_history)

    def test_known_pre_call_failure_retries_without_reconciliation(self) -> None:
        scenario = replace(
            self.timeout_after_ticket,
            recovery_strategy=RecoveryStrategy.RECONCILE_THEN_RETRY,
            injection=Injection(
                "read_telemetry",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.PROVIDER_UNAVAILABLE,
            ),
        )

        result = self.run_scenario(scenario)

        self.assertEqual(RecoveryAction.RETRY, result.recovery_action)
        self.assertEqual(1, result.side_effect_count)
        self.assertEqual(
            ("INJECTED_PROVIDER_UNAVAILABLE", "SUCCESS"),
            result.attempt_history,
        )

    def test_retry_budget_exhaustion_fails_safely(self) -> None:
        scenario = replace(
            self.timeout_after_ticket,
            max_attempts=1,
            injection=Injection(
                "read_telemetry",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.PROVIDER_UNAVAILABLE,
            ),
        )

        with self.assertRaises(RecoveryFailure) as raised:
            self.run_scenario(scenario)

        self.assertEqual("RETRY_BUDGET_EXHAUSTED", raised.exception.code)
        self.assertEqual(
            "INJECTED_PROVIDER_UNAVAILABLE", raised.exception.cause_code
        )
        self.assertEqual(1, raised.exception.attempts)
        self.assertEqual(0, self.ledger.count(scenario.request.idempotency_key))

    def test_malformed_output_is_never_retried(self) -> None:
        scenario = replace(
            self.timeout_after_ticket,
            max_attempts=3,
            recovery_strategy=RecoveryStrategy.RECONCILE_THEN_RETRY,
            injection=Injection(
                "decide_ticket",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.MALFORMED_OUTPUT,
            ),
        )

        with self.assertRaises(RecoveryFailure) as raised:
            self.run_scenario(scenario)

        self.assertEqual("DECISION_INVALID", raised.exception.code)
        self.assertEqual(1, raised.exception.attempts)
        self.assertEqual(0, raised.exception.retries)
        self.assertEqual(0, self.ledger.count(scenario.request.idempotency_key))

    def test_process_interruption_resumes_from_durable_checkpoint(self) -> None:
        scenario = replace(
            self.timeout_after_ticket,
            recovery_strategy=RecoveryStrategy.NAIVE_RETRY,
            injection=Injection(
                "checkpoint",
                2,
                LifecyclePoint.AFTER_CHECKPOINT,
                FailureKind.PROCESS_INTERRUPTION,
            ),
        )

        result = self.run_scenario(scenario)

        self.assertEqual(RecoveryAction.RESUME, result.recovery_action)
        self.assertEqual(1, result.checkpoint_resumes)
        self.assertEqual(1, result.side_effect_count)


if __name__ == "__main__":
    unittest.main()
