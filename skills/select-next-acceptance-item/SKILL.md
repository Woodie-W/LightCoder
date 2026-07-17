---
name: select-next-acceptance-item
description: Choose the next acceptance item that maximizes dependency progress and verifiability. Use only when the LightCoder controller dispatches SELECT_NEXT_ACCEPTANCE_ITEM.
---

# SELECT_NEXT_ACCEPTANCE_ITEM

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Feature Flow Contract`](../references/feature-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- feature.acceptance_items
- feature.contract
- feature.integration_state

## Entry Criteria

- The controller must dispatch `SELECT_NEXT_ACCEPTANCE_ITEM` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.acceptance_items`, `feature.contract`, `feature.integration_state`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Filter unresolved items whose prerequisites are satisfied.
2. Prefer a thin end-to-end behavior over isolated infrastructure.
3. Select one primary item and any inseparable supporting item.
4. Record why it is next and how it will be tested.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `feature.active_acceptance_item`, `feature.selection_reason`, `feature.item_oracle`.
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
- Route guard applied: -> `PLAN_VERTICAL_INCREMENT`
- The proposed route is one of: `PLAN_VERTICAL_INCREMENT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.active_acceptance_item
- feature.selection_reason
- feature.item_oracle

## Routes

- `PLAN_VERTICAL_INCREMENT`

## Constraints

- Do not batch unrelated acceptance items.
