"""Deterministic failure injection at explicit lifecycle points."""

from __future__ import annotations

from collections import defaultdict

from failurebench.models import BenchmarkError
from failurebench.scenarios import FailureKind, Injection, LifecyclePoint


class InjectedFailure(BenchmarkError):
    def __init__(self, injection: Injection):
        self.injection = injection
        super().__init__(f"INJECTED_{injection.failure.value.upper()}")


class FaultInjector:
    def __init__(self, injection: Injection | None = None):
        self.injection = injection
        self.invocations: defaultdict[str, int] = defaultdict(int)
        self.fired = False

    def _fire(
        self, operation: str, lifecycle_point: LifecyclePoint, occurrence: int
    ) -> FailureKind | None:
        injection = self.injection
        if (
            injection is None
            or self.fired
            or injection.operation != operation
            or injection.lifecycle_point != lifecycle_point
            or injection.occurrence != occurrence
        ):
            return None
        self.fired = True
        if injection.failure == FailureKind.MALFORMED_OUTPUT:
            return injection.failure
        raise InjectedFailure(injection)

    def before_call(self, operation: str) -> FailureKind | None:
        self.invocations[operation] += 1
        return self._fire(
            operation,
            LifecyclePoint.BEFORE_CALL,
            self.invocations[operation],
        )

    def after_side_effect(self, operation: str) -> None:
        self._fire(
            operation,
            LifecyclePoint.AFTER_SIDE_EFFECT,
            self.invocations[operation],
        )

    def before_checkpoint(self) -> None:
        self.invocations["checkpoint"] += 1
        self._fire(
            "checkpoint",
            LifecyclePoint.BEFORE_CHECKPOINT,
            self.invocations["checkpoint"],
        )

    def after_checkpoint(self) -> None:
        self._fire(
            "checkpoint",
            LifecyclePoint.AFTER_CHECKPOINT,
            self.invocations["checkpoint"],
        )
