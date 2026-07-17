---
name: apply-transformation-step
description: Apply one controlled refactor or migration step. Use only when the LightCoder controller dispatches APPLY_TRANSFORMATION_STEP.
---

# APPLY_TRANSFORMATION_STEP

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

- transform.active_step
- transform.invariants
- transform.current_revision
- workspace

## Entry Criteria

- The controller must dispatch `APPLY_TRANSFORMATION_STEP` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.active_step`, `transform.invariants`, `transform.current_revision`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Inspect affected symbols and callers immediately before editing.
2. Perform only the selected structural, dependency, API, or configuration change.
3. Update tests or compatibility shims only when required by the target.
4. Record the diff and affected invariants.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `transform.candidate_revision`, `transform.candidate_diff`, `transform.modified_files`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: -> `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`
- The proposed route is one of: `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.candidate_revision
- transform.candidate_diff
- transform.modified_files
- workspace.current_revision
- workspace.dirty_files

## Routes

- `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`

## Constraints

- Do not change intended product behavior during refactoring.
- Do not hide migration failures with broad version pinning unless required.
