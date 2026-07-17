---
name: update-project-state
description: Record accepted milestone progress and refresh the project execution view. Use only when the LightCoder controller dispatches UPDATE_PROJECT_STATE.
---

# UPDATE_PROJECT_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Project Flow Contract`](../references/project-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- project.active_milestone
- project.last_verification
- project.checkpoints

## Entry Criteria

- The controller must dispatch `UPDATE_PROJECT_STATE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.active_milestone`, `project.last_verification`, `project.checkpoints`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Mark verified requirement coverage and milestone status.
2. Update integration state, technical debt, blocked work, and current runnable path.
3. Clear active milestone working data.
4. Create a concise resume summary.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `project.milestones`, `project.requirements_matrix`, `project.integration_state`, `project.technical_debt`, `project.current_summary`.
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
- Route guard applied: -> `CHECK_PROJECT_COMPLETION`
- The proposed route is one of: `CHECK_PROJECT_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.milestones
- project.requirements_matrix
- project.integration_state
- project.technical_debt
- project.current_summary

## Routes

- `CHECK_PROJECT_COMPLETION`

## Constraints

- Do not mark requirements complete without evidence.
