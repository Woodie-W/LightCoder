---
name: select-skill
description: Choose the smallest available skill set capable of completing the active subgoal. Use only when the LightCoder controller dispatches SELECT_SKILL.
---

# SELECT_SKILL

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

- generalist.active_subgoal
- generalist.subgoal_oracle
- skills.registry
- generalist.history

## Entry Criteria

- The controller must dispatch `SELECT_SKILL` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.active_subgoal`, `generalist.subgoal_oracle`, `skills.registry`, `generalist.history`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Match the subgoal to available skills by required action and output.
2. Prefer one primary skill; add supporting skills only when necessary.
3. Check tool availability and required preconditions.
4. Record expected inputs, outputs, and failure signals.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `generalist.selected_skill`, `generalist.skill_plan`, `generalist.skill_selection_reason`.
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
- Route guard applied: executable match/fallback -> `EXECUTE_SUBGOAL`; skill mismatch exposes bad subgoal -> `REVISE_TASK_DECOMPOSITION`
- The proposed route is one of: `EXECUTE_SUBGOAL`, `REVISE_TASK_DECOMPOSITION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.selected_skill
- generalist.skill_plan
- generalist.skill_selection_reason

## Routes

- `EXECUTE_SUBGOAL`
- `REVISE_TASK_DECOMPOSITION`

## Constraints

- Do not select a skill solely by name similarity.
