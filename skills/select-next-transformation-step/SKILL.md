---
name: select-next-transformation-step
description: Choose the next dependency-ordered, independently verifiable transformation step. Use only when the LightCoder controller dispatches SELECT_NEXT_TRANSFORMATION_STEP.
---

# SELECT_NEXT_TRANSFORMATION_STEP

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

- transform.steps
- transform.subtype
- transform.compatibility_matrix
- transform.last_verification

## Entry Criteria

- The controller must dispatch `SELECT_NEXT_TRANSFORMATION_STEP` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.steps`, `transform.subtype`, `transform.compatibility_matrix`, `transform.last_verification`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Select a step whose prerequisites are satisfied.
2. Prefer mechanical or structure-local changes before broad semantic changes.
3. State preserved invariants, expected build impact, and verification command.
4. Record the rollback boundary.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `transform.active_step`, `transform.step_reason`, `transform.step_oracle`.
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
- Route guard applied: step exists -> `APPLY_TRANSFORMATION_STEP`; no steps remain -> `CHECK_TRANSFORM_COMPLETION`
- The proposed route is one of: `APPLY_TRANSFORMATION_STEP`, `CHECK_TRANSFORM_COMPLETION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.active_step
- transform.step_reason
- transform.step_oracle

## Routes

- `APPLY_TRANSFORMATION_STEP`
- `CHECK_TRANSFORM_COMPLETION`

## Constraints

- Do not combine unrelated dependency, API, and refactor changes.
