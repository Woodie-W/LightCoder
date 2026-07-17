---
name: revise-task-decomposition
description: Revise subgoals when the current decomposition is blocked, overlapping, or unverifiable. Use only when the LightCoder controller dispatches REVISE_TASK_DECOMPOSITION.
---

# REVISE_TASK_DECOMPOSITION

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Generalist Flow Contract`](../references/generalist-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- generalist.subgoals
- generalist.unknowns
- generalist.last_verification
- generalist.history

## Entry Criteria

- The controller must dispatch `REVISE_TASK_DECOMPOSITION` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.subgoals`, `generalist.unknowns`, `generalist.last_verification`, `generalist.history`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify the exact decomposition defect.
2. Preserve completed outcomes and confirmed facts.
3. Split, merge, reorder, or replace only affected subgoals.
4. Ensure each new subgoal has a clear local oracle and dependency relation.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `generalist.subgoals`, `generalist.decomposition_history`, `generalist.unknowns`.
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
- Route guard applied: mixed work remains -> `GENERALIST_LOOP_START`; specialized flow now justified -> `ROUTE_TASK`
- The proposed route is one of: `GENERALIST_LOOP_START`, `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.subgoals
- generalist.decomposition_history
- generalist.unknowns

## Routes

- `GENERALIST_LOOP_START`
- `ROUTE_TASK`

## Constraints

- Do not restart from a blank plan.
