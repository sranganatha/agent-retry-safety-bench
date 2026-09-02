import unittest

from agent_retry_safety_bench.models import BenchmarkError
from agent_retry_safety_bench.scenarios import (
    FailureKind,
    LifecyclePoint,
    RecoveryStrategy,
    load_scenario,
    parse_scenario,
)


class ScenarioTest(unittest.TestCase):
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
