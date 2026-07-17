---
name: fix-semantic-incompatibility
description: Correct behavior differences caused by target-version or API semantic changes. Use only when the LightCoder controller dispatches FIX_SEMANTIC_INCOMPATIBILITY.
---

# FIX_SEMANTIC_INCOMPATIBILITY

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

- transform.failure_diagnosis
- transform.compatibility_matrix
- transform.invariants
- workspace

## Entry Criteria

- The controller must dispatch `FIX_SEMANTIC_INCOMPATIBILITY` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.failure_diagnosis`, `transform.compatibility_matrix`, `transform.invariants`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify the precise old/new semantic difference.
2. Implement an adapter, code-path update, or compatibility shim consistent with target requirements.
3. Add a focused compatibility test.
4. Re-run build, behavior, and compatibility checks.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `transform.semantic_fix`, `transform.compatibility_matrix`, `transform.modified_files`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: corrected candidate ready -> `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`; obligation changes plan -> `TRANSFORM_LOOP_START`
- The proposed route is one of: `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`, `TRANSFORM_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.semantic_fix
- transform.compatibility_matrix
- transform.modified_files
- workspace.current_revision
- workspace.dirty_files

## Routes

- `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`
- `TRANSFORM_LOOP_START`

## Constraints

- Do not emulate deprecated behavior when the task explicitly requires the new semantics.
