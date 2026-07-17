---
name: revise-transformation-plan
description: Revise the transformation sequence after behavior regression or invalid assumptions. Use only when the LightCoder controller dispatches REVISE_TRANSFORMATION_PLAN.
---

# REVISE_TRANSFORMATION_PLAN

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Transform Flow Contract`](../references/transform-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- transform.failure_diagnosis
- transform.steps
- transform.invariants
- transform.accepted_steps

## Entry Criteria

- The controller must dispatch `REVISE_TRANSFORMATION_PLAN` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.failure_diagnosis`, `transform.steps`, `transform.invariants`, `transform.accepted_steps`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify the violated invariant or oversized step.
2. Split, reorder, or replace the remaining step while preserving accepted work.
3. Add a targeted equivalence check that would catch the regression earlier.
4. Record the plan revision rationale.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `transform.steps`, `transform.plan_revision_history`, `transform.equivalence_checks`.
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
- Route guard applied: -> `TRANSFORM_LOOP_START`
- The proposed route is one of: `TRANSFORM_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.steps
- transform.plan_revision_history
- transform.equivalence_checks

## Routes

- `TRANSFORM_LOOP_START`

## Constraints

- Do not weaken behavior invariants to fit the candidate.
