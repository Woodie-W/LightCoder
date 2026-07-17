---
name: rollback-to-best-result
description: Restore the last accepted best result after final validation failure. Use only when the LightCoder controller dispatches ROLLBACK_TO_BEST_RESULT.
---

# ROLLBACK_TO_BEST_RESULT

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `deterministic_tool`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.best_result
- optimization.final_validation
- optimization.accepted_candidates

## Entry Criteria

- The controller must dispatch `ROLLBACK_TO_BEST_RESULT` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.best_result`, `optimization.final_validation`, `optimization.accepted_candidates`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify whether the stored best revision or the final measurement caused the failure.
2. Restore the most recent candidate with independently passing correctness.
3. Update the claimed metric to the reproducible result only.
4. Prepare another final validation.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `optimization.best_result`, `optimization.rollback_result`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: restored best is final candidate -> `FINAL_PERFORMANCE_VALIDATION`; no valid best remains -> `OPTIMIZATION_LOOP_START`
- The proposed route is one of: `FINAL_PERFORMANCE_VALIDATION`, `OPTIMIZATION_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.best_result
- optimization.rollback_result
- workspace.current_revision
- workspace.dirty_files

## Routes

- `FINAL_PERFORMANCE_VALIDATION`
- `OPTIMIZATION_LOOP_START`

## Constraints

- Never preserve a faster but incorrect candidate.
