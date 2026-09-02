"""Execute scenarios and emit JSON and Markdown benchmark evidence."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_retry_safety_bench.checkpoints import SQLiteCheckpointStore
from agent_retry_safety_bench.config import load_config
from agent_retry_safety_bench.invariants import InvariantEvidence, evaluate_invariants
from agent_retry_safety_bench.ledger import SQLiteTicketLedger
from agent_retry_safety_bench.recovery import RecoveryFailure, run_with_recovery
from agent_retry_safety_bench.scenarios import Scenario, load_scenario
from agent_retry_safety_bench.tools import DeterministicTools


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: str
    seed: int
    status: str
    ticket_id: str | None
    error_code: str | None
    recovery_strategy: str
    recovery_action: str
    injection_operation: str | None
    injection_occurrence: int | None
    injected_failure: str | None
    lifecycle_point: str | None
    injection_fired: bool
    attempts: int
    retries: int
    checkpoint_resumes: int
    attempt_history: tuple[str, ...]
    side_effect_count: int
    state_history: tuple[str, ...]
    passed_invariants: tuple[str, ...]
    failed_invariants: tuple[str, ...]
    duration_ms: float
    expectations_met: bool


def execute_scenario(scenario: Scenario) -> ScenarioResult:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoints = SQLiteCheckpointStore(root / "checkpoints.db")
        ledger = SQLiteTicketLedger(root / "tickets.db")
        tools = DeterministicTools(load_config("config/demo.json"), ledger)
        started = time.perf_counter_ns()
        try:
            workflow_result = run_with_recovery(scenario, tools, checkpoints)
        except RecoveryFailure as error:
            status = "failed"
            ticket_id = None
            error_code = error.code
            recovery_action = error.action.value
            attempts = error.attempts
            retries = error.retries
            checkpoint_resumes = error.checkpoint_resumes
            attempt_history = error.attempt_history
        else:
            status = workflow_result.status.value
            ticket_id = workflow_result.ticket_id
            error_code = None
            recovery_action = str(workflow_result.recovery_action)
            attempts = workflow_result.attempts
            retries = workflow_result.retries
            checkpoint_resumes = workflow_result.checkpoint_resumes
            attempt_history = workflow_result.attempt_history
        duration_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)

        state_history = checkpoints.history(scenario.request.workflow_id)
        latest = checkpoints.load_latest(scenario.request.workflow_id)
        tickets = ledger.find_by_idempotency_key(scenario.request.idempotency_key)
        invariant_results = evaluate_invariants(
            InvariantEvidence(
                status=status,
                ticket_id=ticket_id,
                attempts=attempts,
                max_attempts=scenario.max_attempts,
                error_code=error_code,
                state_history=state_history,
                ticket_ids=tuple(ticket.id for ticket in tickets),
                request=scenario.request,
                checkpoint_request=latest.request if latest else None,
            )
        )
        passed = tuple(name for name, value in invariant_results.items() if value)
        failed = tuple(name for name, value in invariant_results.items() if not value)
        expected = scenario.expected
        expectations_met = (
            status == expected.status
            and recovery_action == expected.recovery_action.value
            and len(tickets) == expected.side_effect_count
            and invariant_results == expected.invariants
            and (scenario.injection is None or tools.faults.fired)
        )
        injection = scenario.injection
        return ScenarioResult(
            scenario=scenario.name,
            seed=scenario.seed,
            status=status,
            ticket_id=ticket_id,
            error_code=error_code,
            recovery_strategy=scenario.recovery_strategy.value,
            recovery_action=recovery_action,
            injection_operation=injection.operation if injection else None,
            injection_occurrence=injection.occurrence if injection else None,
            injected_failure=injection.failure.value if injection else None,
            lifecycle_point=injection.lifecycle_point.value if injection else None,
            injection_fired=tools.faults.fired,
            attempts=attempts,
            retries=retries,
            checkpoint_resumes=checkpoint_resumes,
            attempt_history=attempt_history,
            side_effect_count=len(tickets),
            state_history=tuple(state.value for state in state_history),
            passed_invariants=passed,
            failed_invariants=failed,
            duration_ms=duration_ms,
            expectations_met=expectations_met,
        )


def _rate(numerator: int, denominator: int) -> str:
    return "n/a" if denominator == 0 else f"{100 * numerator / denominator:.0f}%"


def render_report(results: tuple[ScenarioResult, ...]) -> str:
    lines = [
        "# Agent Retry Safety Bench Report",
        "",
        "Generated from deterministic local fixtures. Durations are diagnostic, not infrastructure performance claims.",
        "A scenario passes when its observed status, action, side effects, and invariants match its fixture; an intentionally unsafe control can therefore pass the benchmark.",
        "Safe recovery rate is the share of injected non-baseline runs that complete while preserving `maximum_one_ticket`; duplicate rate counts runs that violate it.",
        "",
        "## Strategy summary",
        "",
        "| Strategy | Scenarios | Pass rate | Safe recovery rate | Duplicate rate | Retries | Average duration |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    strategies = sorted({result.recovery_strategy for result in results})
    for strategy in strategies:
        group = tuple(result for result in results if result.recovery_strategy == strategy)
        recovery_runs = tuple(
            result
            for result in group
            if result.injection_fired and strategy != "baseline"
        )
        safe = sum(
            result.status == "completed"
            and "maximum_one_ticket" in result.passed_invariants
            for result in recovery_runs
        )
        duplicates = sum(
            "maximum_one_ticket" in result.failed_invariants for result in group
        )
        average_duration = sum(result.duration_ms for result in group) / len(group)
        lines.append(
            f"| {strategy} | {len(group)} | "
            f"{_rate(sum(result.expectations_met for result in group), len(group))} | "
            f"{_rate(safe, len(recovery_runs))} | "
            f"{_rate(duplicates, len(group))} | "
            f"{sum(result.retries for result in group)} | {average_duration:.3f} ms |"
        )

    invariant_names = sorted(
        {name for result in results for name in result.passed_invariants + result.failed_invariants}
    )
    lines.extend(
        [
            "",
            "## Invariant outcomes",
            "",
            "| Strategy | " + " | ".join(invariant_names) + " |",
            "|---|" + "---:|" * len(invariant_names),
        ]
    )
    for strategy in strategies:
        group = tuple(result for result in results if result.recovery_strategy == strategy)
        outcomes = [
            f"{sum(name in result.passed_invariants for result in group)}/{len(group)}"
            for name in invariant_names
        ]
        lines.append(f"| {strategy} | " + " | ".join(outcomes) + " |")

    lines.extend(
        [
            "",
            "## Scenario results",
            "",
            "| Scenario | Status | Strategy | Action | Attempts | Tickets | Failed invariants | Expected |",
            "|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for result in results:
        failed = ", ".join(result.failed_invariants) or "none"
        expected = "yes" if result.expectations_met else "no"
        lines.append(
            f"| {result.scenario} | {result.status} | {result.recovery_strategy} | "
            f"{result.recovery_action} | {result.attempts} | {result.side_effect_count} | "
            f"{failed} | {expected} |"
        )
    return "\n".join(lines) + "\n"


def write_evidence(results: tuple[ScenarioResult, ...], output: str | Path) -> None:
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    for result in results:
        (output_path / f"{result.scenario}.json").write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_path / "report.md").write_text(render_report(results), encoding="utf-8")


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts")
    scenarios = tuple(
        load_scenario(path) for path in sorted(Path("scenarios").glob("*.yaml"))
    )
    results = tuple(execute_scenario(scenario) for scenario in scenarios)
    write_evidence(results, output)
    print(f"wrote {len(results)} scenario results and {output / 'report.md'}")


if __name__ == "__main__":
    main()
