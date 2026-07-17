---
name: implement-minimal-patch
description: Apply the smallest code change that directly tests or fixes the active root-cause hypothesis. Use only when the LightCoder controller dispatches IMPLEMENT_MINIMAL_PATCH.
---

# IMPLEMENT_MINIMAL_PATCH

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.active_hypothesis
- repair.localization
- workspace
- task_profile.risk_flags

## Entry Criteria

- The controller must dispatch `IMPLEMENT_MINIMAL_PATCH` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.active_hypothesis`, `repair.localization`, `workspace`, `task_profile.risk_flags`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Inspect the exact code and tests immediately before editing.
2. Change only the necessary production files; add a regression test when allowed and useful.
3. Preserve public behavior outside the defect and follow local style.
4. Record the diff, intended effect, and rollback point.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `repair.current_patch`, `repair.modified_files`, `repair.patch_rationale`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: candidate exists -> `VERIFY_REPAIR`
- The proposed route is one of: `VERIFY_REPAIR`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.current_patch
- repair.modified_files
- repair.patch_rationale
- workspace.current_revision
- workspace.dirty_files

## Routes

- `VERIFY_REPAIR`

## Constraints

- Do not modify benchmark tests, hidden evaluators, or unrelated code.
- Avoid speculative refactors in a repair patch.
