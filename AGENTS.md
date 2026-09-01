# Repository Instructions

## Goal

Implement only the local benchmark defined in [docs/mvp-spec.md](docs/mvp-spec.md).

The system must prove that recovery from an uncertain agent-tool result does not silently duplicate external side effects or violate explicit safety invariants.

## Scope rules

- Keep the benchmark local, deterministic, and runnable without a paid model or cloud account.
- Build one workflow, one deterministic model stub, one side-effecting tool, one checkpoint store, and one external side-effect ledger.
- Implement only the ten scenarios in the MVP specification until all are deterministic.
- Do not add a UI, Kubernetes, distributed workers, real providers, a general orchestration framework, or a plugin system.
- Prefer the Python standard library, SQLite, and existing dependencies.
- Add a dependency only when a current acceptance criterion cannot be met simply without it.
- Do not create placeholder files, folders, commands, or documents.

## Reliability rules

- Treat a timeout after dispatch as an uncertain outcome, not proof that the side effect failed.
- Keep workflow checkpoints separate from the external side-effect ledger.
- Give every state-changing request a stable idempotency key.
- Reconcile the external system of record before retrying an uncertain write.
- Bound every retry strategy and record every attempt.
- Persist a checkpoint after each successful state transition.
- Never advance to `COMPLETED` after invalid model output or a failed invariant.
- Evaluate success from both workflow outcome and safety invariants.
- Preserve workflow ID and request identity across resume.

## Determinism rules

- Use fixture inputs and a deterministic model stub in the default benchmark.
- Inject failures at named lifecycle points and invocation counts.
- Use a fresh database for independent scenario runs.
- Normalize timestamps and durations before comparing repeated results.
- The same scenario and seed must produce the same logical result.
- Do not use wall-clock timing, network faults, or random sleeps to trigger failures.

## Implementation rules

- Use Python 3.12+ with type annotations.
- Model the five workflow states explicitly; do not hide transitions in prompts.
- Validate scenario files and persisted contracts at their boundaries.
- Use SQLite for checkpoints and the simulated external ticket ledger.
- Keep recovery strategies explicit and independently testable.
- Keep invariant evaluation separate from workflow execution.
- Generate one JSON result per scenario and one consolidated Markdown report.
- One implementation path is enough; do not create interfaces or factories with one implementation.

## Quality gate

Before completing a change:

1. Run formatting and static checks once configured.
2. Run the smallest relevant test, then the full suite.
3. Run the container verification target before opening or merging a pull request once it exists.
4. Confirm failure injection occurred at the intended lifecycle point.
5. Confirm side-effect counts directly from the external ledger.
6. Run affected scenarios repeatedly when changing recovery semantics.
7. Keep README commands truthful; do not document commands that do not work.

Every non-trivial state transition, failure point, recovery rule, and safety invariant needs a runnable test that fails if the rule is removed.

## Change workflow

```text
Issue with acceptance criteria
→ small implementation plan
→ bounded code change
→ independent review
→ Podman checks
→ human approval
```

Do not merge autonomously. Do not combine unrelated implementation phases in one change. Add an ADR only when a real choice has alternatives and lasting consequences.

## Engineering rules

- Keep the happy path flat with validation and guard clauses first.
- Use domain names such as `workflow_state`, `injection_point`, `side_effect_count`, and `recovery_action` instead of vague placeholders.
- Isolate SQLite, file, and tool boundaries from workflow decisions.
- Make invalid states unrepresentable through schemas and explicit state types.
- Separate transition decisions, side effects, persistence, and reporting.
- Return stable machine-readable failure and invariant codes without leaking sensitive payloads.
- Preserve unrelated user changes and remove debugging output before completion.
- Prefer correctness, clarity, testability, safety, and simplicity over speculative extensibility.

## Definition of done

The MVP is done when every scenario in `docs/mvp-spec.md` produces deterministic JSON evidence, the consolidated report clearly contrasts naive retry with reconciliation, all checks pass from a clean checkout using Podman, and the complete demo runs in under three minutes.
