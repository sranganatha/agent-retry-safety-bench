import json
import shutil
import subprocess
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_retry_safety_bench.benchmark import execute_scenario
from agent_retry_safety_bench.scenarios import LifecyclePoint, RecoveryStrategy, load_scenario


class CorpusTest(unittest.TestCase):
    def test_all_ten_scenarios_match_and_repeat(self) -> None:
        # Independent expectations keep a weakened fixture from hiding regressions.
        expected = {
            "baseline": (1, 1, None),
            "timeout-before-telemetry": (2, 1, None),
            "provider-unavailable-recover": (2, 1, None),
            "provider-unavailable-exhausted": (1, 0, "RETRY_BUDGET_EXHAUSTED"),
            "malformed-model-output": (1, 0, "DECISION_INVALID"),
            "timeout-before-ticket": (2, 1, None),
            "timeout-after-ticket-naive": (2, 2, None),
            "timeout-after-ticket-reconcile": (2, 1, None),
            "interruption-after-checkpoint": (2, 1, None),
            "interruption-before-checkpoint": (2, 1, None),
        }
        scenarios = [load_scenario(path) for path in Path("scenarios").glob("*.yaml")]
        self.assertEqual(10, len(scenarios))
        self.assertEqual(set(expected), {scenario.name for scenario in scenarios})
        for scenario in scenarios:
            with self.subTest(scenario=scenario.name):
                result = execute_scenario(scenario)
                self.assertTrue(result.expectations_met)
                self.assertEqual(expected[scenario.name], (
                    result.attempts, result.side_effect_count, result.error_code,
                ))
                self.assertEqual(scenario.injection is not None, result.injection_fired)
                self.assertEqual(
                    ("maximum_one_ticket",) if scenario.name.endswith("-naive") else (),
                    result.failed_invariants,
                )
                first = asdict(result)
                second = asdict(execute_scenario(scenario))
                first.pop("duration_ms")
                second.pop("duration_ms")
                self.assertEqual(first, second)

    def test_safe_resume_at_every_checkpoint_boundary(self) -> None:
        scenario = load_scenario("scenarios/interruption-before-checkpoint.yaml")
        for point in (LifecyclePoint.BEFORE_CHECKPOINT, LifecyclePoint.AFTER_CHECKPOINT):
            for occurrence in range(1, 6):
                with self.subTest(point=point, occurrence=occurrence):
                    result = execute_scenario(replace(
                        scenario,
                        injection=replace(scenario.injection, lifecycle_point=point,
                                          occurrence=occurrence),
                    ))
                    self.assertTrue(result.expectations_met)
                    self.assertEqual("ticket-1001", result.ticket_id)
                    self.assertEqual(
                        ("received", "telemetry_fetched", "decision_made",
                         "ticket_created", "completed"), result.state_history,
                    )
                    self.assertEqual(
                        ("INJECTED_PROCESS_INTERRUPTION", "SUCCESS"),
                        result.attempt_history,
                    )

    def test_naive_resume_reproduces_uncheckpointed_write_duplication(self) -> None:
        scenario = load_scenario("scenarios/interruption-before-checkpoint.yaml")
        result = execute_scenario(replace(
            scenario, recovery_strategy=RecoveryStrategy.NAIVE_RETRY,
        ))
        self.assertEqual(2, result.side_effect_count)
        self.assertEqual(("maximum_one_ticket",), result.failed_invariants)
        self.assertFalse(result.expectations_met)

    def test_command_writes_ten_results_and_rejects_mismatched_expectations(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree("config", root / "config")
            shutil.copytree("scenarios", root / "scenarios")
            command = [sys.executable, "-m", "agent_retry_safety_bench.benchmark"]
            passed = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(0, passed.returncode, passed.stderr)
            self.assertEqual(10, len(list((root / "artifacts").glob("*.json"))))
            self.assertTrue((root / "artifacts/report.md").is_file())
            fixture = root / "scenarios/baseline.yaml"
            raw = json.loads(fixture.read_text(encoding="utf-8"))
            raw["expected"]["side_effect_count"] = 2
            fixture.write_text(json.dumps(raw), encoding="utf-8")
            failed = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(0, failed.returncode)
            evidence = json.loads((root / "artifacts/baseline.json").read_text())
            self.assertFalse(evidence["expectations_met"])

    def test_command_rejects_empty_corpus(self) -> None:
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "agent_retry_safety_bench.benchmark"],
                cwd=directory, capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((Path(directory) / "artifacts/report.md").exists())
