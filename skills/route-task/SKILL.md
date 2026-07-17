---
name: route-task
description: Route the task to one specialized loop or to the generalist fallback using the current TaskProfile. Use only when the LightCoder controller dispatches ROUTE_TASK.
---

# ROUTE_TASK

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Orchestration Flow Contract`](../references/orchestration-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task_profile
- recon_brief
- control.route_history

## Entry Criteria

- The controller must dispatch `ROUTE_TASK` in the `orchestration` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `control.route_history`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Check whether the profile has enough evidence for repair, feature, project, optimize, or transform.
2. Prefer a specialized flow only when its completion oracle matches the task.
3. Use generalist for mixed or low-confidence tasks.
4. Record the routing decision and evidence; prevent route thrashing without new evidence.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `control.active_flow`, `control.route_history`, `control.routing_reason`.
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
- Route guard applied: repair -> `REPAIR_GRAPH`; feature -> `FEATURE_GRAPH`; project -> `PROJECT_GRAPH`; optimize -> `OPTIMIZE_GRAPH`; transform -> `TRANSFORM_GRAPH`; uncertain/mixed -> `GENERALIST_GRAPH`
- The proposed route is one of: `REPAIR_GRAPH`, `FEATURE_GRAPH`, `PROJECT_GRAPH`, `OPTIMIZE_GRAPH`, `TRANSFORM_GRAPH`, `GENERALIST_GRAPH`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- control.active_flow
- control.route_history
- control.routing_reason

## Routes

- `REPAIR_GRAPH`
- `FEATURE_GRAPH`
- `PROJECT_GRAPH`
- `OPTIMIZE_GRAPH`
- `TRANSFORM_GRAPH`
- `GENERALIST_GRAPH`

## Constraints

- Do not perform additional repository exploration unless the profile is insufficient.
- A reroute must cite new evidence.
