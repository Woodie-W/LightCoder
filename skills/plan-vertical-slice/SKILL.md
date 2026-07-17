---
name: plan-vertical-slice
description: Plan a runnable vertical slice for the active milestone. Use only when the LightCoder controller dispatches PLAN_VERTICAL_SLICE.
---

# PLAN_VERTICAL_SLICE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Project Flow Contract`](../references/project-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- project.active_milestone
- project.architecture
- project.module_boundaries
- workspace

## Entry Criteria

- The controller must dispatch `PLAN_VERTICAL_SLICE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.active_milestone`, `project.architecture`, `project.module_boundaries`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Define the end-to-end path and interfaces touched.
2. Break work into a small ordered set of implementation steps.
3. Specify milestone tests, integration checks, and fallback behavior.
4. Confirm the slice fits current external limits.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `project.active_slice.plan`, `project.active_slice.interfaces`, `project.active_slice.tests`, `project.active_slice.done_condition`.
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
- Route guard applied: -> `IMPLEMENT_MILESTONE`
- The proposed route is one of: `IMPLEMENT_MILESTONE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.active_slice.plan
- project.active_slice.interfaces
- project.active_slice.tests
- project.active_slice.done_condition

## Routes

- `IMPLEMENT_MILESTONE`

## Constraints

- Do not plan horizontal completion of every layer before integration.
