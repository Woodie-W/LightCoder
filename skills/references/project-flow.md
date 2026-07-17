# Project Flow Contract

## State

Maintain requirements matrix, architecture decisions, module contracts, milestone DAG, vertical slices, integration state, accepted checkpoints, technical debt, active milestone and final end-to-end oracle.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_PROJECT_STATE` | model-assisted state | requirements matrix, architecture outline, module boundaries, milestone DAG | -> `PROJECT_LOOP_START` |
| `PROJECT_LOOP_START` | deterministic control | ready milestones and external limits | -> `SELECT_NEXT_MILESTONE` |
| `SELECT_NEXT_MILESTONE` | decision | one dependency-ready milestone with requirement coverage | -> `PLAN_VERTICAL_SLICE` |
| `PLAN_VERTICAL_SLICE` | decision | runnable thin slice, interfaces, artifacts and oracle | -> `IMPLEMENT_MILESTONE` |
| `IMPLEMENT_MILESTONE` | action | integrated candidate milestone | -> `VERIFY_MILESTONE_AND_INTEGRATION` |
| `VERIFY_MILESTONE_AND_INTEGRATION` | independent verification | milestone and cross-module evidence | pass -> `CHECKPOINT_PROJECT_STATE`; local failure -> `REPLAN_MILESTONE`; interface failure -> `REVISE_MODULE_BOUNDARIES`; architecture failure -> `REVISE_ARCHITECTURE` |
| `CHECKPOINT_PROJECT_STATE` | deterministic state | restorable accepted revision and coverage update | -> `UPDATE_PROJECT_STATE` |
| `REPLAN_MILESTONE` | decision | smaller/distinct slice with failed assumptions recorded | implementation plan remains valid -> `IMPLEMENT_MILESTONE`; slice changed -> `PLAN_VERTICAL_SLICE` |
| `REVISE_MODULE_BOUNDARIES` | decision | updated interface contracts and affected milestones | slice impact -> `PLAN_VERTICAL_SLICE`; bounded interface fix -> `IMPLEMENT_MILESTONE` |
| `REVISE_ARCHITECTURE` | decision | ADR, migration impact and revised milestone DAG | -> `PROJECT_LOOP_START` |
| `UPDATE_PROJECT_STATE` | deterministic state | milestone status, requirement coverage, debt and next-ready set | -> `CHECK_PROJECT_COMPLETION` |
| `CHECK_PROJECT_COMPLETION` | decision | requirement matrix and integrated runnable state | pending milestone -> `PROJECT_LOOP_START`; type mismatch -> `ROUTE_TASK`; all rows covered -> `RUN_END_TO_END_ACCEPTANCE` |
| `RUN_END_TO_END_ACCEPTANCE` | independent verification | clean primary user journey and mandatory requirement matrix | pass -> `PROJECT_COMPLETE`; fail -> `MAP_FAILURE_TO_MILESTONE` |
| `MAP_FAILURE_TO_MILESTONE` | decision | earliest responsible milestone/interface and failing evidence | -> `PROJECT_LOOP_START` |
| `PROJECT_COMPLETE` | deterministic state | candidate-complete checkpoint | -> `PHASE_3_FINALIZE` |

## Checkpoint requirements

A checkpoint stores accepted revision/tree hash, requirement coverage, module contracts, ADR ids, verification ids, known debt, dirty-tree status and next recommended milestone. Restore verification must prove the revision exists and state references resolve.

## Architecture revision policy

Architecture changes require evidence that a local fix or boundary revision cannot satisfy the milestone. Record alternatives and migration impact. Never rewrite completed milestones without marking their verification stale.
