---
name: rollback-and-diagnose
description: Rollback a failed transformation step and classify the failure precisely. Use only when the LightCoder controller dispatches ROLLBACK_AND_DIAGNOSE.
---

# ROLLBACK_AND_DIAGNOSE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Transform Flow Contract`](../references/transform-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- transform.candidate_revision
- transform.last_verification
- transform.active_step
- transform.current_revision

## Entry Criteria

- The controller must dispatch `ROLLBACK_AND_DIAGNOSE` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.candidate_revision`, `transform.last_verification`, `transform.active_step`, `transform.current_revision`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Preserve logs and diff summary.
2. Restore the latest accepted revision.
3. Determine whether the root issue is build/dependency, behavior, semantic compatibility, or an invalid plan.
4. Record the failed approach and route to the smallest corrective node.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `transform.failed_steps`, `transform.failure_diagnosis`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: build/dependency -> `FIX_BUILD_AND_DEPENDENCIES`; behavior drift -> `REVISE_TRANSFORMATION_PLAN`; semantic compatibility -> `FIX_SEMANTIC_INCOMPATIBILITY`
- The proposed route is one of: `FIX_BUILD_AND_DEPENDENCIES`, `REVISE_TRANSFORMATION_PLAN`, `FIX_SEMANTIC_INCOMPATIBILITY`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.failed_steps
- transform.failure_diagnosis
- workspace.current_revision
- workspace.dirty_files

## Routes

- `FIX_BUILD_AND_DEPENDENCIES`
- `REVISE_TRANSFORMATION_PLAN`
- `FIX_SEMANTIC_INCOMPATIBILITY`

## Constraints

- Do not continue from a failed mixed state.
