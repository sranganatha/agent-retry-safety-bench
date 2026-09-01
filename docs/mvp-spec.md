# MVP Specification

## 1. Purpose

Prove one claim:

> Retrying a failed agent tool is unsafe unless the system can determine whether the external side effect already occurred.

The benchmark passes only when the workflow outcome and every expected safety invariant agree.

## 2. Workflow under test

Use one simulated industrial maintenance workflow:

```text
RECEIVED
   ↓
TELEMETRY_FETCHED
   ↓
DECISION_MADE
   ↓
TICKET_CREATED
   ↓
COMPLETED
```

| State | Responsibility | External side effect |
|---|---|---:|
| `RECEIVED` | Validate the incident request | No |
| `TELEMETRY_FETCHED` | Read deterministic equipment telemetry | No |
| `DECISION_MADE` | Validate the model stub's ticket decision | No |
| `TICKET_CREATED` | Create or reconcile the maintenance ticket | Yes |
| `COMPLETED` | Persist the final workflow result | No |

The default request contains a stable workflow ID, equipment ID, alarm code, and idempotency key. Resume must preserve all four values.

## 3. State and side-effect boundaries

Workflow checkpoints and maintenance tickets represent different systems of record and must be stored separately, even if both use SQLite locally.

A failure before a tool call proves that no tool side effect occurred. A failure after the tool changes external state but before success reaches the caller creates an uncertain outcome. Recovery must query the external ledger by idempotency key before deciding whether to retry.

Checkpoint only completed state transitions. Resuming must load the latest durable state and must not silently move backward or skip required validation.

## 4. Recovery strategies

### `naive_retry`

- Retry a retryable exception within the configured attempt limit.
- Do not reconcile an uncertain side effect.
- Exist only to demonstrate the duplicate-side-effect failure mode.

### `reconcile_then_retry`

- Query the external ledger after an uncertain write result.
- Reuse the existing ticket when the idempotency key is found.
- Retry only when reconciliation proves that no side effect exists.
- Respect the same bounded attempt limit as the baseline strategy.

## 5. Failure model

Required injection points:

| Point | Meaning |
|---|---|
| `before_call` | Fail before invoking the dependency |
| `after_side_effect` | Change external state, then return an error |
| `before_checkpoint` | Complete work in memory, then interrupt before persistence |
| `after_checkpoint` | Persist the transition, then interrupt |

Required failures are timeout, provider unavailable, malformed structured output, and simulated process interruption. Injection is selected by operation name and invocation occurrence, never by timing.

## 6. Safety invariants

| Invariant | Pass condition |
|---|---|
| `maximum_one_ticket` | At most one ticket exists for the idempotency key |
| `retry_budget_respected` | Attempts do not exceed the configured maximum |
| `checkpoint_monotonic` | Resume does not move to an earlier unexpected state |
| `no_completion_on_invalid_output` | Invalid model output cannot produce `COMPLETED` |
| `result_matches_ledger` | The final ticket ID exists in the external ledger |
| `same_request_identity` | Resume preserves workflow and idempotency identifiers |

Implement invariants as executable checks, not prose-only expectations. A completed workflow may still fail the benchmark when an invariant fails.

## 7. Required scenario corpus

| # | Scenario | Expected result |
|---:|---|---|
| 0 | Baseline without failure | Completes with one ticket |
| 1 | Timeout before telemetry call | Retries and completes |
| 2 | Provider unavailable within retry budget | Recovers and completes |
| 3 | Provider unavailable beyond retry budget | Fails safely |
| 4 | Malformed model output | Validation fails; no ticket exists |
| 5 | Timeout before ticket side effect | Retries and creates one ticket |
| 6 | Timeout after ticket side effect with naive retry | Duplicate invariant fails |
| 7 | Timeout after ticket side effect with reconciliation | Completes with one ticket |
| 8 | Process interruption after checkpoint | Resumes from the next state |
| 9 | Process interruption before checkpoint | Repeats safely without duplication |

Do not add scenarios until all ten are deterministic and documented.

## 8. Scenario contract

Each version-controlled YAML scenario defines:

- Name and deterministic seed
- Equipment and alarm fixture inputs
- Recovery strategy and maximum attempts
- Injected operation, occurrence, lifecycle point, and failure
- Expected workflow status and recovery action
- Expected side-effect count and invariants

Add a schema field only when at least two scenarios require it.

## 9. Result evidence

Every scenario produces a JSON result containing:

- Final workflow status
- Recovery strategy and action
- Injected failure and lifecycle point
- Attempts, retries, and checkpoint resumes
- Side-effect count
- Passed and failed invariants
- Execution duration

The consolidated Markdown report compares scenario pass rate, safe recovery rate, duplicate-side-effect rate, retries, recovery duration, and invariant outcomes by strategy. Durations are diagnostic observations, not infrastructure performance claims.

## 10. Demonstration

The final demo must run the same after-side-effect timeout twice:

1. Baseline completes with one ticket.
2. `naive_retry` repeats the uncertain write and fails `maximum_one_ticket`.
3. Fixture state resets.
4. `reconcile_then_retry` finds and reuses the existing ticket.
5. The report shows one unsafe result and one safe recovery result.

The complete demonstration must finish locally in under three minutes.

## 11. Implementation slices

Implement and verify one slice at a time:

1. Python tooling and deterministic configuration
2. Happy-path state machine and tool fixtures
3. SQLite checkpoints and resume
4. Separate side-effect ledger and idempotency
5. Scenario validation and deterministic fault injection
6. Bounded recovery strategies
7. Executable invariants and reporting
8. Ten-scenario corpus and container demo

Do not start a later slice until the current slice has one runnable check.

## 12. Completion check

The MVP is complete when:

- All ten scenarios run without an LLM, network access, or host dependency installation.
- Repeated runs produce identical normalized logical results.
- The unsafe strategy fails for the expected duplicate-side-effect invariant.
- The reconciliation strategy safely recovers from the same uncertain result.
- JSON results and one representative Markdown report are reproducible.
- All checks and the demo pass from a clean checkout using Podman.
- README commands describe only implemented behavior.
