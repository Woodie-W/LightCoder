---
name: rollback-and-reject
description: Reject a failed or non-improving optimization and restore the best accepted state. Use only when the LightCoder controller dispatches ROLLBACK_AND_REJECT.
---

# ROLLBACK_AND_REJECT

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

- optimization.candidate_revision
- optimization.candidate_results
- optimization.best_result

## Entry Criteria

- The controller must dispatch `ROLLBACK_AND_REJECT` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.candidate_revision`, `optimization.candidate_results`, `optimization.best_result`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Classify the rejection reason.
2. Record raw results and insight before rollback.
3. Restore code and configuration to the best accepted revision.
4. Mark the hypothesis rejected with conditions under which it might be revisited.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `optimization.rejected_hypotheses`, `optimization.rollback_result`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: -> `UPDATE_EXPERIMENT_STATE`
- The proposed route is one of: `UPDATE_EXPERIMENT_STATE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.rejected_hypotheses
- optimization.rollback_result
- workspace.current_revision
- workspace.dirty_files

## Routes

- `UPDATE_EXPERIMENT_STATE`

## Constraints

- Do not delete evidence from failed experiments.
