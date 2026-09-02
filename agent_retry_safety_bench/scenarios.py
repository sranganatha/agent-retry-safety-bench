"""Strict contracts for JSON-compatible YAML scenario fixtures."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from agent_retry_safety_bench.models import BenchmarkError, IncidentRequest


class LifecyclePoint(StrEnum):
    BEFORE_CALL = "before_call"
    AFTER_SIDE_EFFECT = "after_side_effect"
    BEFORE_CHECKPOINT = "before_checkpoint"
    AFTER_CHECKPOINT = "after_checkpoint"


class FailureKind(StrEnum):
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_OUTPUT = "malformed_output"
    PROCESS_INTERRUPTION = "process_interruption"


class RecoveryStrategy(StrEnum):
    BASELINE = "baseline"
    NAIVE_RETRY = "naive_retry"
    RECONCILE_THEN_RETRY = "reconcile_then_retry"


class RecoveryAction(StrEnum):
    NONE = "none"
    RETRY = "retry"
    RECONCILE = "reconcile"
    RESUME = "resume"
    FAIL = "fail"


INVARIANTS = {
    "maximum_one_ticket",
    "retry_budget_respected",
    "checkpoint_monotonic",
    "no_completion_on_invalid_output",
    "result_matches_ledger",
    "same_request_identity",
}
OPERATIONS = {"read_telemetry", "decide_ticket", "create_ticket", "checkpoint"}


@dataclass(frozen=True, slots=True)
class Injection:
    operation: str
    occurrence: int
    lifecycle_point: LifecyclePoint
    failure: FailureKind

    def __post_init__(self) -> None:
        if self.operation not in OPERATIONS:
            raise BenchmarkError("SCENARIO_INVALID")
        if isinstance(self.occurrence, bool) or not isinstance(self.occurrence, int):
            raise BenchmarkError("SCENARIO_INVALID")
        if self.occurrence < 1:
            raise BenchmarkError("SCENARIO_INVALID")
        if self.lifecycle_point == LifecyclePoint.AFTER_SIDE_EFFECT:
            valid = self.operation == "create_ticket"
        elif self.lifecycle_point in {
            LifecyclePoint.BEFORE_CHECKPOINT,
            LifecyclePoint.AFTER_CHECKPOINT,
        }:
            valid = self.operation == "checkpoint"
        else:
            valid = self.operation != "checkpoint"
        if not valid:
            raise BenchmarkError("SCENARIO_INVALID")
        if self.failure == FailureKind.MALFORMED_OUTPUT and (
            self.operation != "decide_ticket"
            or self.lifecycle_point != LifecyclePoint.BEFORE_CALL
        ):
            raise BenchmarkError("SCENARIO_INVALID")
        if (
            self.failure == FailureKind.PROCESS_INTERRUPTION
            and self.operation != "checkpoint"
        ):
            raise BenchmarkError("SCENARIO_INVALID")


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    status: str
    recovery_action: RecoveryAction
    side_effect_count: int
    invariants: dict[str, bool]

    def __post_init__(self) -> None:
        if self.status not in {"completed", "failed"}:
            raise BenchmarkError("SCENARIO_INVALID")
        if (
            isinstance(self.side_effect_count, bool)
            or not isinstance(self.side_effect_count, int)
            or self.side_effect_count < 0
        ):
            raise BenchmarkError("SCENARIO_INVALID")
        if set(self.invariants) != INVARIANTS or any(
            not isinstance(value, bool) for value in self.invariants.values()
        ):
            raise BenchmarkError("SCENARIO_INVALID")


@dataclass(frozen=True, slots=True)
class Scenario:
    version: int
    name: str
    seed: int
    request: IncidentRequest
    recovery_strategy: RecoveryStrategy
    max_attempts: int
    injection: Injection | None
    expected: ExpectedOutcome

    def __post_init__(self) -> None:
        if (
            isinstance(self.version, bool)
            or self.version != 1
            or not isinstance(self.name, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.name) is None
        ):
            raise BenchmarkError("SCENARIO_INVALID")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise BenchmarkError("SCENARIO_INVALID")
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise BenchmarkError("SCENARIO_INVALID")


def _exact(raw: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != keys:
        raise BenchmarkError("SCENARIO_INVALID")
    return raw


def parse_scenario(raw: object) -> Scenario:
    try:
        data = _exact(
            raw,
            {
                "version",
                "name",
                "seed",
                "request",
                "recovery_strategy",
                "max_attempts",
                "injection",
                "expected",
            },
        )
        request = _exact(
            data["request"],
            {"workflow_id", "equipment_id", "alarm_code", "idempotency_key"},
        )
        injection_raw = data["injection"]
        injection = None
        if injection_raw is not None:
            injection_data = _exact(
                injection_raw,
                {"operation", "occurrence", "lifecycle_point", "failure"},
            )
            injection = Injection(
                operation=injection_data["operation"],
                occurrence=injection_data["occurrence"],
                lifecycle_point=LifecyclePoint(injection_data["lifecycle_point"]),
                failure=FailureKind(injection_data["failure"]),
            )
        expected_data = _exact(
            data["expected"],
            {"status", "recovery_action", "side_effect_count", "invariants"},
        )
        invariants = _exact(expected_data["invariants"], INVARIANTS)
        return Scenario(
            version=data["version"],
            name=data["name"],
            seed=data["seed"],
            request=IncidentRequest(**request),
            recovery_strategy=RecoveryStrategy(data["recovery_strategy"]),
            max_attempts=data["max_attempts"],
            injection=injection,
            expected=ExpectedOutcome(
                status=expected_data["status"],
                recovery_action=RecoveryAction(expected_data["recovery_action"]),
                side_effect_count=expected_data["side_effect_count"],
                invariants=invariants,
            ),
        )
    except (BenchmarkError, TypeError, ValueError) as error:
        raise BenchmarkError("SCENARIO_INVALID") from error


def load_scenario(path: str | Path) -> Scenario:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkError("SCENARIO_INVALID") from error
    return parse_scenario(raw)


def main() -> None:
    paths = [Path(path) for path in sys.argv[1:]] or sorted(
        Path("scenarios").glob("*.yaml")
    )
    if not paths:
        raise BenchmarkError("SCENARIO_NOT_FOUND")
    scenarios = [load_scenario(path) for path in paths]
    print(f"loaded {len(scenarios)} scenarios")


if __name__ == "__main__":
    main()
