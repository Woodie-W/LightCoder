---
name: run-correctness-and-performance-tests
description: Evaluate a candidate for correctness and statistically credible metric change. Use only when the LightCoder controller dispatches RUN_CORRECTNESS_AND_PERFORMANCE_TESTS.
---

# RUN_CORRECTNESS_AND_PERFORMANCE_TESTS

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

- optimization.candidate_revision
- optimization.metric_spec
- optimization.correctness_baseline
- optimization.performance_baseline

## Entry Criteria

- The controller must dispatch `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.candidate_revision`, `optimization.metric_spec`, `optimization.correctness_baseline`, `optimization.performance_baseline`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the required correctness checks first.
2. If correct, run the configured repeated measurements and capture raw values.
3. Compare with the current best using the task-appropriate summary and variance.
4. Classify as significant improvement, no improvement, correctness failure, or unstable measurement.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `optimization.candidate_results`, `optimization.correctness_results`, `optimization.comparison`, `optimization.result_class`.
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
- Route guard applied: correct+accepted improvement -> `ACCEPT_CANDIDATE`; correct/no improvement or incorrect -> `ROLLBACK_AND_REJECT`; excessive variance -> `STABILIZE_AND_RETEST`
- The proposed route is one of: `ACCEPT_CANDIDATE`, `ROLLBACK_AND_REJECT`, `STABILIZE_AND_RETEST`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.candidate_results
- optimization.correctness_results
- optimization.comparison
- optimization.result_class

## Routes

- `ACCEPT_CANDIDATE`
- `ROLLBACK_AND_REJECT`
- `STABILIZE_AND_RETEST`

## Constraints

- Do not compare single noisy measurements when repeats are configured.
