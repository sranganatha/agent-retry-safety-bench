import json
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agent_retry_safety_bench.benchmark import execute_scenario, render_report, write_evidence
from agent_retry_safety_bench.models import TicketDecision
from agent_retry_safety_bench.tools import DeterministicTools
from agent_retry_safety_bench.scenarios import (
    FailureKind,
    Injection,
    LifecyclePoint,
    load_scenario,
)


class BenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = load_scenario("scenarios/baseline.yaml")
        self.naive = load_scenario("scenarios/timeout-after-ticket.yaml")
        self.reconcile = load_scenario(
            "scenarios/timeout-after-ticket-reconcile.yaml"
        )

    def test_invariants_distinguish_naive_retry_from_reconciliation(self) -> None:
        naive = execute_scenario(self.naive)
        reconcile = execute_scenario(self.reconcile)

        self.assertEqual(("maximum_one_ticket",), naive.failed_invariants)
        self.assertEqual(2, naive.side_effect_count)
        self.assertEqual((), reconcile.failed_invariants)
        self.assertEqual(1, reconcile.side_effect_count)
        self.assertTrue(naive.expectations_met)
        self.assertTrue(reconcile.expectations_met)

    def test_invalid_model_output_fails_without_a_ticket(self) -> None:
        malformed = replace(
            self.naive,
            name="malformed-model-output",
            injection=Injection(
                "decide_ticket",
                1,
                LifecyclePoint.BEFORE_CALL,
                FailureKind.MALFORMED_OUTPUT,
            ),
        )

        result = execute_scenario(malformed)

        self.assertEqual("failed", result.status)
        self.assertEqual("DECISION_INVALID", result.error_code)
        self.assertEqual(0, result.side_effect_count)
        self.assertIn("no_completion_on_invalid_output", result.passed_invariants)

    def test_logical_results_repeat_after_duration_normalization(self) -> None:
        first = asdict(execute_scenario(self.naive))
        second = asdict(execute_scenario(self.naive))
        first.pop("duration_ms")
        second.pop("duration_ms")

        self.assertEqual(first, second)

    def test_writes_one_json_result_per_scenario_and_one_report(self) -> None:
        results = tuple(
            execute_scenario(scenario)
            for scenario in (self.baseline, self.naive, self.reconcile)
        )
        with TemporaryDirectory() as directory:
            output = Path(directory)
            write_evidence(results, output)

            json_files = sorted(output.glob("*.json"))
            report = (output / "report.md").read_text(encoding="utf-8")
            naive = json.loads(
                (output / "timeout-after-ticket-naive.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(3, len(json_files))
        self.assertEqual(["maximum_one_ticket"], naive["failed_invariants"])
        self.assertIn("| naive_retry |", report)
        self.assertIn("| reconcile_then_retry |", report)
        self.assertIn("Safe recovery rate", report)

    def test_report_is_stable_for_fixed_results(self) -> None:
        results = (execute_scenario(self.baseline),)

        self.assertEqual(render_report(results), render_report(results))

    def test_invariant_catches_completion_when_decision_validation_is_bypassed(self) -> None:
        # Mutate the real decision contract; keep workflow, storage, and reporting real.
        with patch.object(TicketDecision, "__post_init__", return_value=None):
            with patch.object(
                DeterministicTools, "decide_ticket",
                return_value=TicketDecision("yes", "Non-boolean decision"),
            ):
                result = execute_scenario(self.baseline)

        self.assertEqual("completed", result.status)
        self.assertIsNone(result.error_code)
        self.assertEqual(("no_completion_on_invalid_output",), result.failed_invariants)
        self.assertFalse(result.expectations_met)


if __name__ == "__main__":
    unittest.main()
