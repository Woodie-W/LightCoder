---
name: stabilize-and-retest
description: Reduce measurement noise without changing the candidate semantics, then retest. Use only when the LightCoder controller dispatches STABILIZE_AND_RETEST.
---

# STABILIZE_AND_RETEST

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.candidate_revision
- optimization.candidate_results
- optimization.metric_spec
- external_run_config

## Entry Criteria

- The controller must dispatch `STABILIZE_AND_RETEST` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.candidate_revision`, `optimization.candidate_results`, `optimization.metric_spec`, `external_run_config`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify likely noise sources such as warmup, competing load, cache state, nondeterminism, or insufficient duration.
2. Apply only measurement-environment corrections allowed by the benchmark.
3. Repeat correctness and performance measurements under the same candidate.
4. If variance remains excessive, classify the candidate inconclusive.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `optimization.measurement_adjustments`, `optimization.candidate_results`, `optimization.result_class`.
- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash.

## Failure Handling

- Preserve partial logs and the exact failure signature; do not silently broaden the patch after a deterministic failure.
- Restore the rollback point before abandoning a candidate when the node contract requires a clean accepted state.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: environment stabilized -> `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`; comparable measurement impossible -> `ROLLBACK_AND_REJECT`
- The proposed route is one of: `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`, `ROLLBACK_AND_REJECT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.measurement_adjustments
- optimization.candidate_results
- optimization.result_class

## Routes

- `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`
- `ROLLBACK_AND_REJECT`

## Constraints

- Do not tune the workload to favor the candidate.
