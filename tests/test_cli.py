import contextlib
import io
import json
import unittest

from failurebench.cli import main


class BaselineCliTest(unittest.TestCase):
    def test_cli_prints_deterministic_completed_result(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            main()

        result = json.loads(output.getvalue())
        self.assertEqual("wf-123", result["workflow_id"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("ticket-1001", result["ticket_id"])
        self.assertEqual(1, result["side_effect_count"])


if __name__ == "__main__":
    unittest.main()
