---
name: replan-repair
description: Recover from a stalled or invalid repair direction using accumulated evidence. Use only when the LightCoder controller dispatches REPLAN_REPAIR.
---

# REPLAN_REPAIR

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

- repair.attempts
- repair.hypotheses
- repair.localization
- repair.last_verification

## Entry Criteria

- The controller must dispatch `REPLAN_REPAIR` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.attempts`, `repair.hypotheses`, `repair.localization`, `repair.last_verification`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify why the last direction failed: reproduction, localization, hypothesis, patch scope, or environment.
2. Preserve confirmed facts and rejected paths.
3. Choose one materially different next strategy and its expected information gain.
4. Rollback harmful or noisy changes before continuing.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `repair.replan_reason`, `repair.next_strategy`, `repair.current_patch`, `workspace.current_revision`, `workspace.dirty_files`.
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
- Route guard applied: repair remains viable -> `REPAIR_LOOP_START`; new evidence changes task type -> `ROUTE_TASK`
- The proposed route is one of: `REPAIR_LOOP_START`, `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.replan_reason
- repair.next_strategy
- repair.current_patch
- workspace.current_revision
- workspace.dirty_files

## Routes

- `REPAIR_LOOP_START`
- `ROUTE_TASK`

## Constraints

- Do not reset the entire state or repeat the same strategy verbatim.
