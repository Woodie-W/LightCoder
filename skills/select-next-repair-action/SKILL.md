---
name: select-next-repair-action
description: Choose the next repair action from the evidence gap, not from a fixed sequence. Use only when the LightCoder controller dispatches SELECT_NEXT_REPAIR_ACTION.
---

# SELECT_NEXT_REPAIR_ACTION

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
- repair.reproduction
- repair.localization
- repair.hypotheses
- repair.last_verification

## Entry Criteria

- The controller must dispatch `SELECT_NEXT_REPAIR_ACTION` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.failure_signature`, `repair.reproduction`, `repair.localization`, `repair.hypotheses`, `repair.last_verification`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. If the problem is not reproduced, choose reproduction or environment inspection.
2. If reproduction exists but the relevant code path is unclear, choose localization.
3. If the path is localized but causality is unclear, form a falsifiable root-cause hypothesis.
4. If a hypothesis has a direct test, choose a minimal patch.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `repair.next_action`, `repair.action_reason`.
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
- Route guard applied: no reproduction -> `REPRODUCE_OR_INSPECT`; broad path -> `LOCALIZE_RELEVANT_CODE`; no falsifiable cause -> `FORM_ROOT_CAUSE_HYPOTHESIS`; testable active hypothesis -> `IMPLEMENT_MINIMAL_PATCH`
- The proposed route is one of: `REPRODUCE_OR_INSPECT`, `LOCALIZE_RELEVANT_CODE`, `FORM_ROOT_CAUSE_HYPOTHESIS`, `IMPLEMENT_MINIMAL_PATCH`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.next_action
- repair.action_reason

## Routes

- `REPRODUCE_OR_INSPECT`
- `LOCALIZE_RELEVANT_CODE`
- `FORM_ROOT_CAUSE_HYPOTHESIS`
- `IMPLEMENT_MINIMAL_PATCH`

## Constraints

- Select one primary action per iteration.
