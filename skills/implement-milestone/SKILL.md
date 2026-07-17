---
name: implement-milestone
description: Implement the active milestone as a working vertical slice. Use only when the LightCoder controller dispatches IMPLEMENT_MILESTONE.
---

# IMPLEMENT_MILESTONE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Project Flow Contract`](../references/project-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- project.active_milestone
- project.active_slice
- project.architecture
- workspace

## Entry Criteria

- The controller must dispatch `IMPLEMENT_MILESTONE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.active_milestone`, `project.active_slice`, `project.architecture`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Create or extend the planned modules and interfaces.
2. Keep the system runnable after each meaningful edit.
3. Add milestone-level tests or executable checks.
4. Record architecture deviations and technical debt explicitly.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `project.active_milestone.diff`, `project.modified_files`, `project.architecture_deviations`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: -> `VERIFY_MILESTONE_AND_INTEGRATION`
- The proposed route is one of: `VERIFY_MILESTONE_AND_INTEGRATION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.active_milestone.diff
- project.modified_files
- project.architecture_deviations
- workspace.current_revision
- workspace.dirty_files

## Routes

- `VERIFY_MILESTONE_AND_INTEGRATION`

## Constraints

- Do not silently change module contracts or global architecture.
