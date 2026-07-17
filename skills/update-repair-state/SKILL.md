---
name: update-repair-state
description: Commit the latest repair evidence to structured state. Use only when the LightCoder controller dispatches UPDATE_REPAIR_STATE.
---

# UPDATE_REPAIR_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.current_patch
- repair.last_verification
- repair.evidence
- workspace

## Entry Criteria

- The controller must dispatch `UPDATE_REPAIR_STATE` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.current_patch`, `repair.last_verification`, `repair.evidence`, `workspace`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Append the attempt with hypothesis, diff summary, commands, result, and timestamp.
2. Update reproduced/fixed/regression flags and the current best revision.
3. Mark confirmed and rejected hypotheses.
4. Compress stale details into a short evidence summary without losing commands or outcomes.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `repair.attempts`, `repair.status_flags`, `repair.hypotheses`, `repair.best_revision`, `repair.current_summary`.
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
- Route guard applied: -> `CHECK_REPAIR_COMPLETION`
- The proposed route is one of: `CHECK_REPAIR_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.attempts
- repair.status_flags
- repair.hypotheses
- repair.best_revision
- repair.current_summary

## Routes

- `CHECK_REPAIR_COMPLETION`

## Constraints

- Keep raw logs by reference rather than copying them into state.
