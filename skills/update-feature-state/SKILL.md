---
name: update-feature-state
description: Record accepted feature progress and prepare the next loop. Use only when the LightCoder controller dispatches UPDATE_FEATURE_STATE.
---

# UPDATE_FEATURE_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Feature Flow Contract`](../references/feature-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- feature.active_acceptance_item
- feature.active_increment
- feature.last_verification

## Entry Criteria

- The controller must dispatch `UPDATE_FEATURE_STATE` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.active_acceptance_item`, `feature.active_increment`, `feature.last_verification`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Mark the item complete only with verification evidence.
2. Append the increment summary, tests, revision, and affected interfaces.
3. Update integration state and remaining dependencies.
4. Refresh the concise feature progress summary.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `feature.acceptance_items`, `feature.increments`, `feature.integration_state`, `feature.current_summary`, `feature.best_revision`.
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
- Route guard applied: -> `CHECK_FEATURE_COMPLETION`
- The proposed route is one of: `CHECK_FEATURE_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.acceptance_items
- feature.increments
- feature.integration_state
- feature.current_summary
- feature.best_revision

## Routes

- `CHECK_FEATURE_COMPLETION`

## Constraints

- Do not preserve an unverified increment as accepted.
