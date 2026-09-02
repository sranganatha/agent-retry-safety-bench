import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from failurebench.checkpoints import SQLiteCheckpointStore
from failurebench.config import BenchmarkConfig, load_config
from failurebench.ledger import SQLiteTicketLedger
from failurebench.models import BenchmarkError, IncidentRequest, TicketDecision
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


class TicketLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "tickets.db"
        self.ledger = SQLiteTicketLedger(self.path)
        self.request = IncidentRequest(
            "wf-123", "etch-101", "TEMP_HIGH", "wf-123:create-ticket"
        )
        self.decision = TicketDecision(True, "Investigate TEMP_HIGH on etch-101")

    def test_ticket_persists_and_is_found_by_idempotency_key(self) -> None:
        created = self.ledger.create(self.request, self.decision)

        reopened = SQLiteTicketLedger(self.path)
        self.assertEqual("ticket-1001", created.id)
        self.assertEqual((created,), reopened.find_by_idempotency_key(self.request.idempotency_key))
        self.assertEqual(1, reopened.count(self.request.idempotency_key))

    def test_repeated_write_remains_visible_for_duplicate_detection(self) -> None:
        first = self.ledger.create(self.request, self.decision)
        second = self.ledger.create(self.request, self.decision)

        self.assertEqual(("ticket-1001", "ticket-1002"), (first.id, second.id))
        self.assertEqual(2, self.ledger.count(self.request.idempotency_key))

    def test_completed_workflow_reads_count_from_reopened_ledger(self) -> None:
        checkpoints = SQLiteCheckpointStore(
            Path(self.directory.name) / "checkpoints.db"
        )
        tools = DeterministicTools(load_config("config/demo.json"), self.ledger)
        MaintenanceWorkflow(tools, checkpoints).run(self.request)

        reopened_tools = DeterministicTools(
            load_config("config/demo.json"), SQLiteTicketLedger(self.path)
        )
        result = MaintenanceWorkflow(reopened_tools, checkpoints).run(self.request)

        self.assertEqual("ticket-1001", result.ticket_id)
        self.assertEqual(1, result.side_effect_count)

    def test_workflow_rejects_shared_checkpoint_and_ledger_database(self) -> None:
        checkpoints = SQLiteCheckpointStore(self.path)
        tools = DeterministicTools(BenchmarkConfig(version=1, equipment=()), self.ledger)

        with self.assertRaisesRegex(BenchmarkError, "STORAGE_BOUNDARY_INVALID"):
            MaintenanceWorkflow(tools, checkpoints)

    def test_invalid_persisted_ticket_is_rejected(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO tickets (equipment_id, reason, idempotency_key)
                VALUES ('', 'reason', 'request-key')
                """
            )

        with self.assertRaisesRegex(BenchmarkError, "TICKET_LEDGER_INVALID"):
            self.ledger.find_by_idempotency_key("request-key")


if __name__ == "__main__":
    unittest.main()
