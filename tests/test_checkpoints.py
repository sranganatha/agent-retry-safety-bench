import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from failurebench.checkpoints import Checkpoint, SQLiteCheckpointStore
from failurebench.config import BenchmarkConfig, load_config
from failurebench.models import (
    BenchmarkError,
    IncidentRequest,
    Telemetry,
    TicketDecision,
    WorkflowState,
)
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


class CheckpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "checkpoints.db"
        self.store = SQLiteCheckpointStore(self.path)
        self.request = IncidentRequest(
            "wf-123", "etch-101", "TEMP_HIGH", "wf-123:create-ticket"
        )
        self.telemetry = Telemetry("etch-101", 87.5, ("TEMP_HIGH",))
        self.decision = TicketDecision(True, "Investigate TEMP_HIGH on etch-101")

    def test_workflow_persists_every_completed_transition(self) -> None:
        tools = DeterministicTools(load_config("config/demo.json"))

        result = MaintenanceWorkflow(tools, self.store).run(self.request)

        self.assertEqual(tuple(WorkflowState), self.store.history("wf-123"))
        self.assertEqual(WorkflowState.COMPLETED, result.status)

    def test_resume_continues_after_latest_checkpoint(self) -> None:
        self.store.save(Checkpoint(self.request, WorkflowState.RECEIVED))
        self.store.save(
            Checkpoint(
                self.request,
                WorkflowState.TELEMETRY_FETCHED,
                self.telemetry,
            )
        )
        tools = DeterministicTools(BenchmarkConfig(version=1, equipment=()))

        result = MaintenanceWorkflow(tools, self.store).run(self.request)

        self.assertEqual(WorkflowState.COMPLETED, result.status)
        self.assertEqual(tuple(WorkflowState), result.state_history)
        self.assertEqual(1, result.side_effect_count)

    def test_resume_rejects_changed_request_identity(self) -> None:
        self.store.save(Checkpoint(self.request, WorkflowState.RECEIVED))
        changed = IncidentRequest(
            "wf-123", "etch-101", "PRESSURE_HIGH", "wf-123:create-ticket"
        )

        with self.assertRaisesRegex(BenchmarkError, "REQUEST_IDENTITY_MISMATCH"):
            MaintenanceWorkflow(
                DeterministicTools(load_config("config/demo.json")), self.store
            ).run(changed)

    def test_resume_preserves_valid_no_ticket_decision(self) -> None:
        self.store.save(Checkpoint(self.request, WorkflowState.RECEIVED))
        self.store.save(
            Checkpoint(
                self.request,
                WorkflowState.TELEMETRY_FETCHED,
                self.telemetry,
            )
        )
        self.store.save(
            Checkpoint(
                self.request,
                WorkflowState.DECISION_MADE,
                self.telemetry,
                TicketDecision(False, "Alarm is not active"),
            )
        )
        tools = DeterministicTools(BenchmarkConfig(version=1, equipment=()))

        with self.assertRaisesRegex(BenchmarkError, "ALARM_NOT_ACTIVE"):
            MaintenanceWorkflow(tools, self.store).run(self.request)

        self.assertEqual([], tools.tickets)

    def test_store_rejects_skipped_and_backward_transitions(self) -> None:
        received = Checkpoint(self.request, WorkflowState.RECEIVED)
        fetched = Checkpoint(
            self.request, WorkflowState.TELEMETRY_FETCHED, self.telemetry
        )
        decided = Checkpoint(
            self.request,
            WorkflowState.DECISION_MADE,
            self.telemetry,
            self.decision,
        )
        self.store.save(received)

        with self.assertRaisesRegex(BenchmarkError, "CHECKPOINT_NON_MONOTONIC"):
            self.store.save(decided)

        self.store.save(fetched)
        with self.assertRaisesRegex(BenchmarkError, "CHECKPOINT_NON_MONOTONIC"):
            self.store.save(received)

    def test_store_rejects_invalid_persisted_state(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "wf-bad",
                    0,
                    "unknown",
                    "etch-101",
                    "TEMP_HIGH",
                    "wf-bad:create-ticket",
                    None,
                    None,
                    None,
                ),
            )

        with self.assertRaisesRegex(BenchmarkError, "CHECKPOINT_INVALID"):
            self.store.load_latest("wf-bad")


if __name__ == "__main__":
    unittest.main()
