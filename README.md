# Agent Retry Safety Bench

[![CI](https://github.com/sranganatha/agent-retry-safety-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/sranganatha/agent-retry-safety-bench/actions/workflows/ci.yml)

A reproducible benchmark for measuring retry safety in stateful agent workflows.

> Retrying a failed agent tool is unsafe unless the system can determine whether the external side effect already occurred.

## Why this exists

Agent failures become dangerous when the caller cannot tell whether a state-changing tool completed. A timeout after a successful write can look identical to a timeout before the write; blindly retrying may create duplicate payments, infrastructure changes, messages, or maintenance records.

Agent Retry Safety Bench makes that reliability problem deterministic, visible, and measurable. Its concrete example is an industrial maintenance workflow that reads equipment telemetry and creates a maintenance ticket, but the recovery pattern applies to any agent that changes external state.

## Benchmark workflow

```text
Load scenario
      ↓
Run explicit state machine
      ↓
Inject a configured failure
      ↓
Checkpoint and recover
      ↓
Reconcile uncertain side effects
      ↓
Evaluate safety invariants
      ↓
Generate JSON and Markdown evidence
```

The portfolio demonstration compares two strategies against the same timeout after ticket creation:

1. `naive_retry` repeats the write and fails the duplicate-side-effect invariant.
2. `reconcile_then_retry` checks the external ledger, finds the completed write, and finishes without duplication.

## Local MVP

- One five-state maintenance-ticket workflow
- One deterministic model stub and telemetry fixture
- One side-effecting maintenance tool
- SQLite checkpoints and a separate side-effect ledger
- Failure injection at exact lifecycle points
- Two bounded recovery strategies
- Ten deterministic scenarios
- Machine-readable invariants and reports
- One command-line demonstration

## Scope

This is a local correctness and safety benchmark, not a general-purpose agent framework, production workflow engine, observability platform, prompt benchmark, or infrastructure chaos system. It requires no paid model, cloud account, distributed workers, UI, or real equipment integration.

## Run the demo

From a checkout, with Git, Make, and a running Podman machine:

```bash
podman info
make test-container
make report
```

After the image is built, `make report` is the complete one-command demo: it runs all ten scenarios in isolated databases and writes ten JSON results and a [consolidated report](artifacts/report.md) to `artifacts/`. Expect `10/10 scenarios matched expectations`. The command exits nonzero for unexpected outcomes; the deliberately unsafe duplicate-write control is an expected outcome, not a safe recovery. `make run` runs only the baseline workflow.

No host Python installation or paid service is required. Image building downloads Python/build dependencies; scenario execution itself works offline. The demo runtime target is under three minutes after image setup; diagnostic durations vary and are excluded from logical repeatability comparisons.

## What the fixtures prove

The [ten-scenario corpus](docs/mvp-spec.md#7-required-scenario-corpus) covers pre-call timeouts, provider failure with/without retry budget, invalid model output, uncertain writes, and checkpoint interruptions. Before the ticket checkpoint, safe resume reconciles the durable ledger; after that checkpoint, it resumes without repeating the write.

The safe runner checks durable state before every attempt, including a new invocation with reopened databases. A `decision_made` checkpoint means a ticket write may be outstanding: reconciliation must succeed before re-execution, regardless of the injected failure type or location. Fresh-runner and checkpoint-timeout regressions verify this boundary. This is a single-runner model, not a concurrent exactly-once protocol; attempt budgets and fault schedules are per invocation.

The invalid-output invariant checks the persisted decision's boolean and nonblank-reason contract independently of the final exception code. A mutation test bypasses decision validation and proves that a completed run still fails this invariant.

Failures are one-shot deterministic injections. The exhausted-provider case sets `max_attempts: 1` (no retry remaining), not a sustained outage. Process interruption is an exception at a named checkpoint boundary, not an OS process kill; no distributed exactly-once or real-provider claims are made. The matched timeout pair demonstrates the strategy difference; aggregate rates across different fixtures are not a controlled performance comparison.

## Design references

- [MVP specification](docs/mvp-spec.md)
- [Repository rules](AGENTS.md)
