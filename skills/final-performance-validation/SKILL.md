---
name: final-performance-validation
description: Revalidate the best result from a clean state using the final measurement protocol. Use only when the LightCoder controller dispatches FINAL_PERFORMANCE_VALIDATION.
---

# FINAL_PERFORMANCE_VALIDATION

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.best_result
- optimization.metric_spec
- optimization.correctness_baseline

## Entry Criteria

- The controller must dispatch `FINAL_PERFORMANCE_VALIDATION` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.best_result`, `optimization.metric_spec`, `optimization.correctness_baseline`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Restore the best revision in a clean process/environment.
2. Run the full correctness suite required by the task.
3. Repeat the final performance measurement independently.
4. Compare against the original baseline and verify the claimed improvement is stable.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `optimization.final_validation`, `optimization.final_delta`, `optimization.final_evidence`.
- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash.

## Failure Handling

- A timeout, missing dependency, flaky measurement, or unavailable service is inconclusive until classified.
- Never repair the candidate inside a verifier attempt; route the evidence back to an action or diagnosis node.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: pass -> `OPTIMIZATION_COMPLETE`; fail -> `ROLLBACK_TO_BEST_RESULT`
- The proposed route is one of: `OPTIMIZATION_COMPLETE`, `ROLLBACK_TO_BEST_RESULT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.final_validation
- optimization.final_delta
- optimization.final_evidence

## Routes

- `OPTIMIZATION_COMPLETE`
- `ROLLBACK_TO_BEST_RESULT`

## Constraints

- Do not report the best exploratory measurement as the final result.
