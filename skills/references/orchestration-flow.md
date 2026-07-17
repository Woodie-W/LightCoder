# Orchestration Flow

## Node guards

| Node | Mode | Success evidence / output | Legal route guard |
| --- | --- | --- | --- |
| `START` | deterministic control | valid task, workspace, frozen config, run/session ids | always `PHASE_1_QUICK_RECON` |
| `PHASE_1_QUICK_RECON` | model-assisted inspection | TaskProfile, repo/build map, baseline revision, explicit unknowns | profile schema valid -> `ROUTE_TASK` |
| `ROUTE_TASK` | model-assisted decision | selected flow, confidence, cited evidence | repair -> `REPAIR_GRAPH`; feature -> `FEATURE_GRAPH`; project -> `PROJECT_GRAPH`; optimize -> `OPTIMIZE_GRAPH`; transform -> `TRANSFORM_GRAPH`; uncertain/mixed -> `GENERALIST_GRAPH` |
| `REPAIR_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_REPAIR_STATE`; resumed flow -> `REPAIR_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `FEATURE_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_FEATURE_STATE`; resumed flow -> `FEATURE_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `PROJECT_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_PROJECT_STATE`; resumed flow -> `PROJECT_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `OPTIMIZE_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_OPTIMIZATION_STATE`; resumed flow -> `OPTIMIZATION_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `TRANSFORM_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_TRANSFORM_STATE`; resumed flow -> `TRANSFORM_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `GENERALIST_GRAPH` | deterministic control | initialized active flow | new flow -> `INITIALIZE_GENERALIST_STATE`; resumed flow -> `GENERALIST_LOOP_START`; new type evidence -> `ROUTE_TASK`; candidate complete -> `PHASE_3_FINALIZE` |
| `PHASE_2_TASK_LOOP` | virtual grouping | groups the six Phase 2 subgraphs for diagrams and reporting | never dispatched; listed routes describe aggregate edges only |
| `PHASE_3_FINALIZE` | deterministic control | candidate-complete revision and completion evidence | -> `RUN_CLEAN_ENVIRONMENT_VALIDATION` |
| `END` | deterministic delivery | final validated revision equals delivery revision | terminal completed/failed/cancelled status |

## Routing predicates

- **repair**: a concrete observed behavior violates an existing contract and restoration is the primary deliverable.
- **feature**: the existing system must gain one or more explicit acceptance behaviors without project-scale architecture construction.
- **project**: success requires multiple milestones/modules and an integrated runnable system.
- **optimize**: correctness is fixed and success is defined by a reproducible quantitative metric.
- **transform**: refactor/migration/compatibility work must preserve declared invariants.
- **generalist**: mixed work, weak oracle, documentation/configuration, or insufficient classification evidence.

Prefer generalist over a low-confidence specialized route. Record the rejected alternatives. A reroute requires new evidence and increments `control.route_changes`; more than two evidence-free route changes is a stall.

## Recon limits

Recon should inspect the task, repository root, README, build/dependency configuration, test entry points, and up to five task-relevant areas. It may run cheap version/status commands but does not run the task baseline or modify files.

## Terminal policy

`END` verifies that all final gates are already recorded. It does not run new validation or edit artifacts. Terminal failure must distinguish product failure, infrastructure block, external limit, cancellation, and missing user input.
