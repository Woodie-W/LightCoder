---
name: phase-2-task-loop
description: Run the currently selected specialized task loop and preserve resumable state. Documentation-only virtual grouping for PHASE_2_TASK_LOOP; the controller must never dispatch it.
---

# PHASE_2_TASK_LOOP

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `control`
- Execution mode: `deterministic`
- Virtual node: `true`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md), [`Shared State Contract`](../references/state-contract.md), and [`Orchestration Flow Contract`](../references/orchestration-flow.md) for diagram/reporting semantics.
- Never dispatch this node, create an attempt, call a model/tool, produce a `NodeResult`, or write state. Its routes are aggregate documentation edges only.
<!-- runtime-contract:end -->

## Input State

- control.active_flow
- task_profile
- control.subgraph_state
- external_run_config

## Entry Criteria

- `PHASE_2_TASK_LOOP` is documentation-only and must not receive an attempt id.
- Reporting and visualization code may read the declared inputs to aggregate concrete subgraph status.
- Runtime dispatch to this node is always a controller/manifest error.

## Procedure

1. Represent the six concrete Phase 2 subgraphs as one visual and reporting group.
2. Aggregate status, iteration, checkpoint, and evidence metrics without flattening specialized state.
3. Document that runtime routing enters a concrete `*_GRAPH` directly and never enters this virtual node.

## Evidence And Artifacts

- Do not create attempts, evidence, state patches, context, or repository artifacts for this node.
- Derive aggregate status only from committed concrete-subgraph state and events.

## Failure Handling

- Reject runtime dispatch without changing state.
- Recover by selecting the concrete graph already named by `control.active_flow`.

## Exit Checklist

- No `NodeResult`, state patch, evidence, or runtime route is emitted.
- Aggregate route meaning: never dispatched; listed routes describe aggregate edges only.
- Diagram edges are `REPAIR_GRAPH`, `FEATURE_GRAPH`, `PROJECT_GRAPH`, `OPTIMIZE_GRAPH`, `TRANSFORM_GRAPH`, `GENERALIST_GRAPH`, `ROUTE_TASK`, `PHASE_3_FINALIZE` and are never runtime proposals from this node.

## State Updates

None. This virtual node never writes state.

## Routes

- `REPAIR_GRAPH`
- `FEATURE_GRAPH`
- `PROJECT_GRAPH`
- `OPTIMIZE_GRAPH`
- `TRANSFORM_GRAPH`
- `GENERALIST_GRAPH`
- `ROUTE_TASK`
- `PHASE_3_FINALIZE`

## Constraints

- Do not replace the specialized loop with a generic ReAct loop.
