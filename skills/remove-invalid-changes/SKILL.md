---
name: remove-invalid-changes
description: Remove unrelated, unsafe, non-reproducible, or integrity-violating final changes. Use only when the LightCoder controller dispatches REMOVE_INVALID_CHANGES.
---

# REMOVE_INVALID_CHANGES

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Finalize Flow Contract`](../references/finalize-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- final_review.invalid_changes
- integrity.findings
- workspace.accepted_revision
- workspace

## Entry Criteria

- The controller must dispatch `REMOVE_INVALID_CHANGES` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `final_review.invalid_changes`, `integrity.findings`, `workspace.accepted_revision`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. For each finding, decide whether to remove, regenerate correctly, or route back to Phase 2.
2. Remove temporary files, secrets, caches, benchmark tampering, and unrelated edits.
3. Preserve necessary source changes and evidence.
4. Record exactly what was removed and why.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `final_review.remediation`, `workspace.current_revision`, `workspace.dirty_files`, `workspace.accepted_revision`.
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
- Route guard applied: cleanup complete -> `RUN_CLEAN_ENVIRONMENT_VALIDATION`; issue belongs to implementation flow -> `ROUTE_FAILURE_BACK`
- The proposed route is one of: `RUN_CLEAN_ENVIRONMENT_VALIDATION`, `ROUTE_FAILURE_BACK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- final_review.remediation
- workspace.current_revision
- workspace.dirty_files
- workspace.accepted_revision

## Routes

- `RUN_CLEAN_ENVIRONMENT_VALIDATION`
- `ROUTE_FAILURE_BACK`

## Constraints

- Do not remove a required artifact merely to make the diff smaller.
