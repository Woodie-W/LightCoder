---
name: update-generalist-state
description: Record a verified subgoal and refresh global progress. Use only when the LightCoder controller dispatches UPDATE_GENERALIST_STATE.
---

# UPDATE_GENERALIST_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Generalist Flow Contract`](../references/generalist-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- generalist.active_subgoal
- generalist.execution_result
- generalist.last_verification

## Entry Criteria

- The controller must dispatch `UPDATE_GENERALIST_STATE` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.active_subgoal`, `generalist.execution_result`, `generalist.last_verification`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Mark the subgoal complete with evidence.
2. Append artifacts, revision, commands, and learned constraints.
3. Unblock dependent subgoals and update outcomes.
4. Clear active execution state and refresh the concise summary.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `generalist.subgoals`, `generalist.outcomes`, `generalist.history`, `generalist.current_summary`, `generalist.best_revision`.
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
- Route guard applied: -> `CHECK_GLOBAL_COMPLETION`
- The proposed route is one of: `CHECK_GLOBAL_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.subgoals
- generalist.outcomes
- generalist.history
- generalist.current_summary
- generalist.best_revision

## Routes

- `CHECK_GLOBAL_COMPLETION`

## Constraints

- Do not accept unverified code changes.
