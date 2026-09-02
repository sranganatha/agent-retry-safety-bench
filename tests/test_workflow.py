import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from failurebench.checkpoints import SQLiteCheckpointStore
from failurebench.config import load_config
from failurebench.models import BenchmarkError, IncidentRequest, WorkflowState
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


class HappyPathWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tools = DeterministicTools(load_config("config/demo.json"))
        self.checkpoints = SQLiteCheckpointStore(
            Path(self.directory.name) / "checkpoints.db"
        )

    @staticmethod
    def request(
        equipment_id: str = "etch-101", alarm_code: str = "TEMP_HIGH"
    ) -> IncidentRequest:
        return IncidentRequest(
            workflow_id="wf-123",
            equipment_id=equipment_id,
            alarm_code=alarm_code,
            idempotency_key="wf-123:create-ticket",
        )

    def test_baseline_follows_all_states_and_creates_one_ticket(self) -> None:
        result = MaintenanceWorkflow(self.tools, self.checkpoints).run(self.request())

        self.assertEqual(WorkflowState.COMPLETED, result.status)
        self.assertEqual("ticket-1001", result.ticket_id)
        self.assertEqual("baseline", result.recovery_strategy)
        self.assertEqual(1, result.side_effect_count)
        self.assertEqual(
            tuple(WorkflowState),
            result.state_history,
        )
        self.assertEqual(1, len(self.tools.tickets))
        self.assertEqual("wf-123:create-ticket", self.tools.tickets[0].idempotency_key)

    def test_unknown_equipment_stops_before_ticket_creation(self) -> None:
        workflow = MaintenanceWorkflow(self.tools, self.checkpoints)

        with self.assertRaisesRegex(BenchmarkError, "EQUIPMENT_NOT_FOUND"):
            workflow.run(self.request(equipment_id="missing"))

        self.assertEqual(WorkflowState.RECEIVED, workflow.state)
        self.assertEqual([], self.tools.tickets)

    def test_inactive_alarm_stops_before_ticket_creation(self) -> None:
        workflow = MaintenanceWorkflow(self.tools, self.checkpoints)

        with self.assertRaisesRegex(BenchmarkError, "ALARM_NOT_ACTIVE"):
            workflow.run(self.request(equipment_id="etch-201"))

        self.assertEqual(WorkflowState.DECISION_MADE, workflow.state)
        self.assertEqual([], self.tools.tickets)

    def test_invalid_request_is_rejected(self) -> None:
        with self.assertRaisesRegex(BenchmarkError, "REQUEST_INVALID"):
            IncidentRequest("", "etch-101", "TEMP_HIGH", "request-1")


if __name__ == "__main__":
    unittest.main()
