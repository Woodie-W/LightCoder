---
name: update-transform-state
description: Record accepted transformation progress and prepare the next cycle. Use only when the LightCoder controller dispatches UPDATE_TRANSFORM_STATE.
---

# UPDATE_TRANSFORM_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Transform Flow Contract`](../references/transform-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- transform.active_step
- transform.last_verification
- transform.accepted_steps

## Entry Criteria

- The controller must dispatch `UPDATE_TRANSFORM_STATE` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.active_step`, `transform.last_verification`, `transform.accepted_steps`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Update completed steps, compatibility matrix, current revision, and remaining risks.
2. Clear candidate-only state.
3. Refresh a concise summary of preserved invariants and next step.
4. Persist the accepted checkpoint.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `transform.steps`, `transform.compatibility_matrix`, `transform.current_summary`, `control.last_checkpoint`.
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
- Route guard applied: -> `CHECK_TRANSFORM_COMPLETION`
- The proposed route is one of: `CHECK_TRANSFORM_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.steps
- transform.compatibility_matrix
- transform.current_summary
- control.last_checkpoint

## Routes

- `CHECK_TRANSFORM_COMPLETION`

## Constraints

- Do not mark a step complete without all step checks.
