import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from failurebench.checkpoints import SQLiteCheckpointStore
from failurebench.config import load_config
from failurebench.faults import FaultInjector, InjectedFailure
from failurebench.ledger import SQLiteTicketLedger
from failurebench.models import BenchmarkError, IncidentRequest, WorkflowState
from failurebench.scenarios import FailureKind, Injection, LifecyclePoint
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


class FaultInjectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.checkpoints = SQLiteCheckpointStore(root / "checkpoints.db")
        self.ledger = SQLiteTicketLedger(root / "tickets.db")
        self.request = IncidentRequest(
            "wf-123", "etch-101", "TEMP_HIGH", "wf-123:create-ticket"
        )

    @staticmethod
    def injection(
        operation: str,
        occurrence: int,
        lifecycle_point: LifecyclePoint,
        failure: FailureKind,
    ) -> Injection:
        return Injection(operation, occurrence, lifecycle_point, failure)

    def tools(self, injection: Injection) -> DeterministicTools:
        return DeterministicTools(
            load_config("config/demo.json"),
            self.ledger,
            FaultInjector(injection),
        )

    def test_before_call_fires_only_on_configured_occurrence(self) -> None:
        faults = FaultInjector(
            self.injection(
                "read_telemetry", 2, LifecyclePoint.BEFORE_CALL, FailureKind.TIMEOUT
            )
        )

        faults.before_call("read_telemetry")
        with self.assertRaisesRegex(InjectedFailure, "INJECTED_TIMEOUT"):
            faults.before_call("read_telemetry")

        self.assertTrue(faults.fired)
        self.assertEqual(2, faults.invocations["read_telemetry"])

    def test_provider_unavailable_has_stable_failure_code(self) -> None:
        faults = FaultInjector(
            self.injection(
                "read_telemetry",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.PROVIDER_UNAVAILABLE,
            )
        )

        with self.assertRaisesRegex(
            InjectedFailure, "INJECTED_PROVIDER_UNAVAILABLE"
        ):
            faults.before_call("read_telemetry")

    def test_after_side_effect_failure_leaves_ticket_durable(self) -> None:
        tools = self.tools(
            self.injection(
                "create_ticket",
                1,
                LifecyclePoint.AFTER_SIDE_EFFECT,
                FailureKind.TIMEOUT,
            )
        )

        with self.assertRaisesRegex(InjectedFailure, "INJECTED_TIMEOUT"):
            MaintenanceWorkflow(tools, self.checkpoints).run(self.request)

        self.assertEqual(1, self.ledger.count(self.request.idempotency_key))
        self.assertEqual(
            WorkflowState.DECISION_MADE,
            self.checkpoints.load_latest("wf-123").state,
        )

    def test_before_checkpoint_failure_does_not_persist_transition(self) -> None:
        tools = self.tools(
            self.injection(
                "checkpoint",
                2,
                LifecyclePoint.BEFORE_CHECKPOINT,
                FailureKind.PROCESS_INTERRUPTION,
            )
        )

        with self.assertRaisesRegex(InjectedFailure, "INJECTED_PROCESS_INTERRUPTION"):
            MaintenanceWorkflow(tools, self.checkpoints).run(self.request)

        self.assertEqual(
            WorkflowState.RECEIVED,
            self.checkpoints.load_latest("wf-123").state,
        )
        self.assertEqual(0, self.ledger.count(self.request.idempotency_key))

    def test_after_checkpoint_failure_persists_transition_for_resume(self) -> None:
        tools = self.tools(
            self.injection(
                "checkpoint",
                2,
                LifecyclePoint.AFTER_CHECKPOINT,
                FailureKind.PROCESS_INTERRUPTION,
            )
        )
        with self.assertRaisesRegex(InjectedFailure, "INJECTED_PROCESS_INTERRUPTION"):
            MaintenanceWorkflow(tools, self.checkpoints).run(self.request)

        self.assertEqual(
            WorkflowState.TELEMETRY_FETCHED,
            self.checkpoints.load_latest("wf-123").state,
        )
        resumed = DeterministicTools(load_config("config/demo.json"), self.ledger)
        result = MaintenanceWorkflow(resumed, self.checkpoints).run(self.request)

        self.assertEqual(WorkflowState.COMPLETED, result.status)
        self.assertEqual(1, result.side_effect_count)

    def test_malformed_output_fails_model_contract_before_write(self) -> None:
        tools = self.tools(
            self.injection(
                "decide_ticket",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.MALFORMED_OUTPUT,
            )
        )

        with self.assertRaisesRegex(BenchmarkError, "DECISION_INVALID"):
            MaintenanceWorkflow(tools, self.checkpoints).run(self.request)

        self.assertTrue(tools.faults.fired)
        self.assertEqual(0, self.ledger.count(self.request.idempotency_key))


if __name__ == "__main__":
    unittest.main()
