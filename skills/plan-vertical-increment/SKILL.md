---
name: plan-vertical-increment
description: Plan the smallest end-to-end change that satisfies the selected acceptance item. Use only when the LightCoder controller dispatches PLAN_VERTICAL_INCREMENT.
---

# PLAN_VERTICAL_INCREMENT

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

- feature.active_acceptance_item
- feature.contract
- recon_brief
- workspace

## Entry Criteria

- The controller must dispatch `PLAN_VERTICAL_INCREMENT` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.active_acceptance_item`, `feature.contract`, `recon_brief`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Trace the required path across interface, core logic, persistence/integration, and output as applicable.
2. List files and interfaces to modify, tests to add or run, and compatibility constraints.
3. Define a rollback boundary and a clear done condition.
4. Keep the plan short enough to execute in one loop.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `feature.active_increment.plan`, `feature.active_increment.files`, `feature.active_increment.tests`, `feature.active_increment.done_condition`.
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
- Route guard applied: feasible bounded slice -> `IMPLEMENT_INCREMENT`
- The proposed route is one of: `IMPLEMENT_INCREMENT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.active_increment.plan
- feature.active_increment.files
- feature.active_increment.tests
- feature.active_increment.done_condition

## Routes

- `IMPLEMENT_INCREMENT`

## Constraints

- Do not create architecture work unrelated to the acceptance item.
