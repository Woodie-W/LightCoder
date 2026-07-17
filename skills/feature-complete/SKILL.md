---
name: feature-complete
description: Seal the accepted feature implementation for finalization. Use only when the LightCoder controller dispatches FEATURE_COMPLETE.
---

# FEATURE_COMPLETE

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

- feature.completion_evidence
- feature.increments
- feature.acceptance_results

## Entry Criteria

- The controller must dispatch `FEATURE_COMPLETE` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.completion_evidence`, `feature.increments`, `feature.acceptance_results`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Freeze the accepted revision.
2. Summarize delivered behavior, interfaces, acceptance coverage, regressions, and remaining risks.
3. Mark the feature subgraph complete.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `feature.status`, `feature.final_summary`, `workspace.accepted_revision`.
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
- Route guard applied: -> `PHASE_3_FINALIZE`
- The proposed route is one of: `PHASE_3_FINALIZE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.status
- feature.final_summary
- workspace.accepted_revision

## Routes

- `PHASE_3_FINALIZE`

## Constraints

- Do not add new functionality in this node.
