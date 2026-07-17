---
name: checkpoint-project-state
description: Persist an accepted milestone in a resumable project checkpoint. Use only when the LightCoder controller dispatches CHECKPOINT_PROJECT_STATE.
---

# CHECKPOINT_PROJECT_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic_tool`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Project Flow Contract`](../references/project-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- project.active_milestone
- project.last_verification
- workspace

## Entry Criteria

- The controller must dispatch `CHECKPOINT_PROJECT_STATE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.active_milestone`, `project.last_verification`, `workspace`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Create a stable revision or commit for the accepted milestone.
2. Save requirement coverage, architecture decisions, module contracts, tests, known debt, and next recommended milestone.
3. Reference large logs and artifacts rather than embedding them.
4. Verify the checkpoint can be restored.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `project.checkpoints`, `project.best_revision`, `project.milestones`, `control.last_checkpoint`.
- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state.

## Failure Handling

- On revision conflict, discard the proposed patch, reload, and recompute; never merge stale state heuristically.
- Reject dangling evidence, artifact, work-item, or revision references without partially committing state.
- A persistence, schema, or lease failure interrupts the attempt; it is not product evidence and must not consume a business retry.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: -> `UPDATE_PROJECT_STATE`
- The proposed route is one of: `UPDATE_PROJECT_STATE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.checkpoints
- project.best_revision
- project.milestones
- control.last_checkpoint

## Routes

- `UPDATE_PROJECT_STATE`

## Constraints

- Checkpoint only verified states.
