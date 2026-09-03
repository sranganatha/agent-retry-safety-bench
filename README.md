# Agent Retry Safety Bench

[![CI](https://github.com/sranganatha/agent-retry-safety-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/sranganatha/agent-retry-safety-bench/actions/workflows/ci.yml)

A reproducible benchmark for measuring retry safety in stateful agent workflows.

> Blindly retrying a non-idempotent tool after an uncertain outcome can duplicate external side effects.

The benchmark compares two strategies against the same timeout after ticket creation:

| Same post-write timeout | Tickets created | `maximum_one_ticket` invariant |
|---|---:|---|
| Naive retry | 2 | Fails |
| Reconcile then retry | 1 | Passes |

See the [scenario results](artifacts/report.md#scenario-results) and [JSON evidence](artifacts/).

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
Recover using the selected strategy
      ↓
Evaluate safety invariants
      ↓
Generate JSON and Markdown evidence
```

1. `naive_retry` repeats the write and fails the duplicate-side-effect invariant.
2. `reconcile_then_retry` checks the external ledger, finds the completed write, and finishes without duplication.

## What's implemented

- Five-state maintenance workflow with deterministic telemetry and model output
- Durable SQLite checkpoints, separate ticket ledger, and stable request identity
- Bounded naive-retry and reconcile-before-retry strategies
- Ten reproducible failure scenarios covering timeouts, invalid output,
  provider unavailability, and checkpoint interruptions
- Six executable invariants checking duplication, retry budgets,
  checkpoint order, decision validity, ledger consistency, and request identity
- Offline container execution with per-scenario JSON evidence and a Markdown report

## Scope

This is a local correctness and safety benchmark, not a general-purpose agent framework, production workflow engine, observability platform, prompt benchmark, or infrastructure chaos system. It requires no paid model, cloud account, distributed workers, UI, or real equipment integration.

## Run the demo

With Git, Make, and a running Podman machine:

```bash
podman info
make test-container
make report
```

After the image is built, `make report` is the complete one-command demo: it runs all ten scenarios in isolated databases and writes ten JSON results and a [consolidated report](artifacts/report.md) to `artifacts/`. Expect `10/10 scenarios matched expectations`. The command exits nonzero for unexpected outcomes; the deliberately unsafe duplicate-write control is an expected outcome, not a safe recovery. `make run` runs only the baseline workflow.

No host Python installation or paid service is required. Image building downloads Python/build dependencies; scenario execution itself works offline. The demo runtime target is under three minutes after image setup; diagnostic durations vary and are excluded from logical repeatability comparisons.

## What the fixtures prove

The [ten-scenario corpus](docs/mvp-spec.md#7-required-scenario-corpus) covers pre-call timeouts, provider failure with/without retry budget, invalid model output, uncertain writes, and checkpoint interruptions. Before the ticket checkpoint, safe resume reconciles the durable ledger; after that checkpoint, it resumes without repeating the write.

Safe recovery is tested both within an invocation and with fresh runner objects reopening the databases. This is a single-runner model, not a concurrent exactly-once protocol; attempt budgets and fault schedules are per invocation. The [specification](docs/mvp-spec.md#6-safety-invariants) describes the independent decision-validity check and its mutation test.

Failures are one-shot deterministic injections. The exhausted-provider case sets `max_attempts: 1` (no retry remaining), not a sustained outage. Process interruption is an exception at a named checkpoint boundary, not an OS process kill; no distributed exactly-once or real-provider claims are made. The matched timeout pair demonstrates the strategy difference; aggregate rates across different fixtures are not a controlled performance comparison.

## Design references

- [MVP specification](docs/mvp-spec.md)
- [Repository rules](AGENTS.md)
