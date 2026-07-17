---
name: update-failure-signature
description: Replace the active failure signature when the patch reveals a materially different failure. Use only when the LightCoder controller dispatches UPDATE_FAILURE_SIGNATURE.
---

# UPDATE_FAILURE_SIGNATURE

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

- repair.failure_signature
- repair.new_failure_signature
- repair.last_verification

## Entry Criteria

- The controller must dispatch `UPDATE_FAILURE_SIGNATURE` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.failure_signature`, `repair.new_failure_signature`, `repair.last_verification`.
- Require validated source evidence and compare-and-swap against the input state revision.
- Apply only declared state fields and preserve immutable attempt, failure, and evidence history.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Compare exception type, failing assertion, stack location, output, and triggering input.
2. Preserve the previous signature in history.
3. Record whether the original defect is fixed, masked, or transformed.
4. Set the new signature as active only when reproducible.

## Evidence And Artifacts

- Record the old/new state revisions, applied patch, source evidence ids, affected work items, and invariant checks.
- Change accepted revision only when the referenced verification passed at exactly that revision.
- Proposed state updates are limited to: `repair.failure_history`, `repair.failure_signature`, `repair.progress_assessment`.
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
- Route guard applied: causal clue present -> `FORM_ROOT_CAUSE_HYPOTHESIS`; path changed/unclear -> `LOCALIZE_RELEVANT_CODE`
- The proposed route is one of: `FORM_ROOT_CAUSE_HYPOTHESIS`, `LOCALIZE_RELEVANT_CODE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.failure_history
- repair.failure_signature
- repair.progress_assessment

## Routes

- `FORM_ROOT_CAUSE_HYPOTHESIS`
- `LOCALIZE_RELEVANT_CODE`

## Constraints

- Do not discard the original acceptance criterion.
