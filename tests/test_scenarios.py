import json
import unittest
from itertools import product
from pathlib import Path

from agent_retry_safety_bench.benchmark import execute_scenario
from agent_retry_safety_bench.models import BenchmarkError
from agent_retry_safety_bench.scenarios import (
    FailureKind,
    Injection,
    LifecyclePoint,
    RecoveryStrategy,
    load_scenario,
    parse_scenario,
)


class ScenarioTest(unittest.TestCase):
    def test_supported_fault_combinations_are_safe_and_others_rejected(self) -> None:
        operations = ("read_telemetry", "decide_ticket", "create_ticket", "checkpoint")
        for operation, point, failure in product(operations, LifecyclePoint, FailureKind):
            with self.subTest(operation=operation, point=point, failure=failure):
                raw = json.loads(Path("scenarios/baseline.yaml").read_text())
                raw["recovery_strategy"] = "reconcile_then_retry"
                raw["max_attempts"] = 2
                raw["injection"] = {
                    "operation": operation, "occurrence": 4 if operation == "checkpoint" else 1,
                    "lifecycle_point": point.value, "failure": failure.value,
                }
                location_supported = (
                    (point == LifecyclePoint.BEFORE_CALL and operation != "checkpoint")
                    or (point == LifecyclePoint.AFTER_SIDE_EFFECT and operation == "create_ticket")
                    or (point in (LifecyclePoint.BEFORE_CHECKPOINT, LifecyclePoint.AFTER_CHECKPOINT)
                        and operation == "checkpoint")
                )
                failure_supported = (
                    failure in (FailureKind.TIMEOUT, FailureKind.PROVIDER_UNAVAILABLE)
                    or (failure == FailureKind.PROCESS_INTERRUPTION and operation == "checkpoint")
                    or (failure == FailureKind.MALFORMED_OUTPUT and operation == "decide_ticket"
                        and point == LifecyclePoint.BEFORE_CALL)
                )
                if not (location_supported and failure_supported):
                    with self.assertRaisesRegex(BenchmarkError, "SCENARIO_INVALID"):
                        parse_scenario(raw)
                    continue
                result = execute_scenario(parse_scenario(raw))
                malformed = failure == FailureKind.MALFORMED_OUTPUT
                self.assertTrue(result.injection_fired)
                self.assertEqual("failed" if malformed else "completed", result.status)
                self.assertEqual(0 if malformed else 1, result.side_effect_count)
                self.assertEqual((), result.failed_invariants)

    def test_unknown_direct_injection_enums_are_rejected(self) -> None:
        for point, failure in (
            ("unknown", FailureKind.TIMEOUT),
            (LifecyclePoint.BEFORE_CALL, "unknown"),
        ):
            with self.subTest(point=point, failure=failure):
                with self.assertRaisesRegex(BenchmarkError, "SCENARIO_INVALID"):
                    Injection("read_telemetry", 1, point, failure)

    def test_versioned_fixtures_load_with_strict_contracts(self) -> None:
        baseline = load_scenario("scenarios/baseline.yaml")
        timeout = load_scenario("scenarios/timeout-after-ticket.yaml")

        self.assertEqual(RecoveryStrategy.BASELINE, baseline.recovery_strategy)
        self.assertIsNone(baseline.injection)
        self.assertEqual(FailureKind.TIMEOUT, timeout.injection.failure)
        self.assertEqual(
            LifecyclePoint.AFTER_SIDE_EFFECT,
            timeout.injection.lifecycle_point,
        )
        self.assertFalse(timeout.expected.invariants["maximum_one_ticket"])

    def test_unknown_or_missing_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(BenchmarkError, "SCENARIO_INVALID"):
            parse_scenario({"version": 1, "unexpected": True})

    def test_impossible_injection_combination_is_rejected(self) -> None:
        raw = {
            "version": 1,
            "name": "invalid",
            "seed": 0,
            "request": {
                "workflow_id": "wf-invalid",
                "equipment_id": "etch-101",
                "alarm_code": "TEMP_HIGH",
                "idempotency_key": "wf-invalid:create-ticket",
            },
            "recovery_strategy": "baseline",
            "max_attempts": 1,
            "injection": {
                "operation": "read_telemetry",
                "occurrence": 0,
                "lifecycle_point": "after_side_effect",
                "failure": "timeout",
            },
            "expected": {
                "status": "failed",
                "recovery_action": "fail",
                "side_effect_count": 0,
                "invariants": {
                    "maximum_one_ticket": True,
                    "retry_budget_respected": True,
                    "checkpoint_monotonic": True,
                    "no_completion_on_invalid_output": True,
                    "result_matches_ledger": True,
                    "same_request_identity": True,
                },
            },
        }

        with self.assertRaisesRegex(BenchmarkError, "SCENARIO_INVALID"):
            parse_scenario(raw)


if __name__ == "__main__":
    unittest.main()
