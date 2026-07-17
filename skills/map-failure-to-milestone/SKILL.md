---
name: map-failure-to-milestone
description: Map an end-to-end failure back to the smallest responsible milestone or boundary. Use only when the LightCoder controller dispatches MAP_FAILURE_TO_MILESTONE.
---

# MAP_FAILURE_TO_MILESTONE

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

- project.acceptance_failures
- project.milestones
- project.module_boundaries
- project.checkpoints

## Entry Criteria

- The controller must dispatch `MAP_FAILURE_TO_MILESTONE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.acceptance_failures`, `project.milestones`, `project.module_boundaries`, `project.checkpoints`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Trace the failed scenario through module boundaries.
2. Identify the earliest violated contract or missing requirement.
3. Reopen only the responsible milestone and dependent milestones.
4. Define a focused reproduction and next vertical slice.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `project.active_milestone`, `project.reopened_milestones`, `project.failure_mapping`, `project.active_slice`.
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
- Route guard applied: -> `PROJECT_LOOP_START`
- The proposed route is one of: `PROJECT_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.active_milestone
- project.reopened_milestones
- project.failure_mapping
- project.active_slice

## Routes

- `PROJECT_LOOP_START`

## Constraints

- Do not reset the entire project plan for a localized failure.
