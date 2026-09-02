# Agent FailureBench

[![CI](https://github.com/sranganatha/agent-failure-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/sranganatha/agent-failure-bench/actions/workflows/ci.yml)

A reproducible benchmark for measuring safe recovery in stateful agent workflows.

> Retrying a failed agent tool is unsafe unless the system can determine whether the external side effect already occurred.

## Why this exists

Agent failures become dangerous when the caller cannot tell whether a state-changing tool completed. A timeout after a successful write can look identical to a timeout before the write; blindly retrying may create duplicate payments, infrastructure changes, messages, or maintenance records.

Agent FailureBench makes that reliability problem deterministic, visible, and measurable. Its concrete example is an industrial maintenance workflow that reads equipment telemetry and creates a maintenance ticket, but the recovery pattern applies to any agent that changes external state.

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

## Planned local MVP

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

## Development status

The executable baseline persists all five workflow states to SQLite, resumes from the latest durable checkpoint, and creates exactly one in-memory maintenance ticket. The external ticket ledger and recovery strategies remain later bounded slices.

## Local verification

Local checks require only a running Podman machine:

```bash
podman info
make test-container
make run
```

No host Python installation is required.

## Design references

- [MVP specification](docs/mvp-spec.md)
- [Repository rules](AGENTS.md)
