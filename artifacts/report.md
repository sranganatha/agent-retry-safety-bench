# Agent Retry Safety Bench Report

Generated from deterministic local fixtures. Durations are diagnostic, not infrastructure performance claims.
A scenario passes when its observed status, action, side effects, and invariants match its fixture; an intentionally unsafe control can therefore pass the benchmark.
Safe recovery rate is the share of injected non-baseline runs that complete while preserving `maximum_one_ticket`; duplicate rate counts runs that violate it.

## Strategy summary

| Strategy | Scenarios | Pass rate | Safe recovery rate | Duplicate rate | Retries | Average duration |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 1 | 100% | n/a | 0% | 0 | 2.710 ms |
| naive_retry | 1 | 100% | 0% | 100% | 1 | 2.752 ms |
| reconcile_then_retry | 1 | 100% | 100% | 0% | 1 | 3.198 ms |

## Invariant outcomes

| Strategy | checkpoint_monotonic | maximum_one_ticket | no_completion_on_invalid_output | result_matches_ledger | retry_budget_respected | same_request_identity |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| naive_retry | 1/1 | 0/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| reconcile_then_retry | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |

## Scenario results

| Scenario | Status | Strategy | Action | Attempts | Tickets | Failed invariants | Expected |
|---|---|---|---|---:|---:|---|---|
| baseline | completed | baseline | none | 1 | 1 | none | yes |
| timeout-after-ticket-reconcile | completed | reconcile_then_retry | reconcile | 2 | 1 | none | yes |
| timeout-after-ticket-naive | completed | naive_retry | retry | 2 | 2 | maximum_one_ticket | yes |
