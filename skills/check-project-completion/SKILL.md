---
name: check-project-completion
description: Decide whether to continue milestones, reroute, or run final end-to-end acceptance. Use only when the LightCoder controller dispatches CHECK_PROJECT_COMPLETION.
---

# CHECK_PROJECT_COMPLETION

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

- project.milestones
- project.requirements_matrix
- project.integration_state
- task_profile

## Entry Criteria

- The controller must dispatch `CHECK_PROJECT_COMPLETION` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.milestones`, `project.requirements_matrix`, `project.integration_state`, `task_profile`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Check all required milestones and requirement rows.
2. Check that a runnable integrated system exists.
3. Detect evidence that the task is better represented by another flow.
4. Route to end-to-end acceptance only when all milestone oracles pass.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `project.completion_decision`, `project.completion_evidence`.
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
- Route guard applied: pending milestone -> `PROJECT_LOOP_START`; type mismatch -> `ROUTE_TASK`; all rows covered -> `RUN_END_TO_END_ACCEPTANCE`
- The proposed route is one of: `PROJECT_LOOP_START`, `ROUTE_TASK`, `RUN_END_TO_END_ACCEPTANCE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.completion_decision
- project.completion_evidence

## Routes

- `PROJECT_LOOP_START`
- `ROUTE_TASK`
- `RUN_END_TO_END_ACCEPTANCE`

## Constraints

- Do not treat scaffolding or partial modules as project completion.
