---
name: initialize-feature-state
description: Create the feature contract and acceptance tracking state. Use only when the LightCoder controller dispatches INITIALIZE_FEATURE_STATE.
---

# INITIALIZE_FEATURE_STATE

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

- task_profile
- recon_brief
- workspace

## Entry Criteria

- The controller must dispatch `INITIALIZE_FEATURE_STATE` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Extract user-visible behavior, inputs, outputs, interfaces, constraints, and compatibility expectations.
2. Create an acceptance matrix with one independently verifiable item per behavior.
3. Identify likely modules and integration boundaries without designing the full implementation.
4. Initialize increments, test evidence, and unresolved ambiguities.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `feature.contract`, `feature.acceptance_items`, `feature.impact_candidates`, `feature.increments`, `feature.unknowns`.
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
- Route guard applied: -> `FEATURE_LOOP_START`
- The proposed route is one of: `FEATURE_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.contract
- feature.acceptance_items
- feature.impact_candidates
- feature.increments
- feature.unknowns

## Routes

- `FEATURE_LOOP_START`

## Constraints

- Do not silently resolve material requirement ambiguity.
