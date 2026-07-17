---
name: form-root-cause-hypothesis
description: Form a falsifiable explanation for the observed failure. Use only when the LightCoder controller dispatches FORM_ROOT_CAUSE_HYPOTHESIS.
---

# FORM_ROOT_CAUSE_HYPOTHESIS

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.failure_signature
- repair.localization
- repair.evidence
- repair.hypotheses

## Entry Criteria

- The controller must dispatch `FORM_ROOT_CAUSE_HYPOTHESIS` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.failure_signature`, `repair.localization`, `repair.evidence`, `repair.hypotheses`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. State the causal mechanism, affected invariant, and why it produces the observed signature.
2. Identify the smallest observation or patch that would confirm or reject it.
3. Compare against prior rejected hypotheses and avoid restating them.
4. Keep at most a few ranked hypotheses; designate one active hypothesis.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `repair.hypotheses`, `repair.active_hypothesis`, `repair.discriminating_check`.
- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state.

## Failure Handling

- If evidence is insufficient, choose a legal evidence-gathering/replan route rather than fabricate certainty.
- If candidates remain tied, prefer the smaller reversible action and record the tie.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: testable -> `IMPLEMENT_MINIMAL_PATCH`; path evidence insufficient -> `LOCALIZE_RELEVANT_CODE`
- The proposed route is one of: `IMPLEMENT_MINIMAL_PATCH`, `LOCALIZE_RELEVANT_CODE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.hypotheses
- repair.active_hypothesis
- repair.discriminating_check

## Routes

- `IMPLEMENT_MINIMAL_PATCH`
- `LOCALIZE_RELEVANT_CODE`

## Constraints

- Do not treat correlation or proximity as root-cause proof.
