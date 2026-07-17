---
name: accept-candidate
description: Promote a correct and meaningfully improved candidate to the new best state. Use only when the LightCoder controller dispatches ACCEPT_CANDIDATE.
---

# ACCEPT_CANDIDATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `state`
- Execution mode: `deterministic_tool`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.candidate_revision
- optimization.candidate_results
- optimization.comparison

## Entry Criteria

- The controller must dispatch `ACCEPT_CANDIDATE` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.candidate_revision`, `optimization.candidate_results`, `optimization.comparison`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Confirm all correctness constraints pass.
2. Confirm the primary metric improves under the configured acceptance rule.
3. Commit or tag the candidate as best.
4. Record the exact delta and retained change.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `optimization.best_result`, `optimization.accepted_candidates`, `workspace.accepted_revision`.
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
- Route guard applied: -> `UPDATE_EXPERIMENT_STATE`
- The proposed route is one of: `UPDATE_EXPERIMENT_STATE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.best_result
- optimization.accepted_candidates
- workspace.accepted_revision

## Routes

- `UPDATE_EXPERIMENT_STATE`

## Constraints

- Do not accept on secondary metrics if the primary criterion fails unless explicitly configured.
