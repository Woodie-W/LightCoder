---
name: check-feature-completion
description: Decide whether all feature acceptance and compatibility obligations are complete. Use only when the LightCoder controller dispatches CHECK_FEATURE_COMPLETION.
---

# CHECK_FEATURE_COMPLETION

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
- feature.integration_state
- feature.regression_results
- task_profile

## Entry Criteria

- The controller must dispatch `CHECK_FEATURE_COMPLETION` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.acceptance_items`, `feature.integration_state`, `feature.regression_results`, `task_profile`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Require every mandatory acceptance item to have passing evidence.
2. Require integration and relevant regression checks to pass.
3. Check unresolved contract unknowns and compatibility risks.
4. Detect whether the task has expanded into project-scale or another flow.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `feature.completion_decision`, `feature.completion_evidence`.
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
- Route guard applied: all pass -> `FEATURE_COMPLETE`; project-scale/type mismatch -> `ROUTE_TASK`; otherwise -> `FEATURE_LOOP_START`
- The proposed route is one of: `FEATURE_COMPLETE`, `FEATURE_LOOP_START`, `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.completion_decision
- feature.completion_evidence

## Routes

- `FEATURE_COMPLETE`
- `FEATURE_LOOP_START`
- `ROUTE_TASK`

## Constraints

- Do not infer completion from code volume or number of iterations.
