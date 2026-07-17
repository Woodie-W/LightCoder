# Transform Flow Contract

## State

Maintain mode (`refactor` or `migration`), target, invariants, behavior/build baselines, compatibility matrix, deprecated items, ordered steps, accepted revision, candidate diff, verification results and deferred cleanup.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_TRANSFORM_STATE` | model-assisted state | mode, target, invariants, compatibility obligations, step outline | refactor -> `CAPTURE_BEHAVIOR_BASELINE`; migration -> `CAPTURE_BUILD_COMPATIBILITY_BASELINE` |
| `CAPTURE_BEHAVIOR_BASELINE` | verification | public behavior, errors, side effects and pre-existing failures | -> `TRANSFORM_LOOP_START` |
| `CAPTURE_BUILD_COMPATIBILITY_BASELINE` | verification | versions, manifests, build/runtime matrix and pre-existing failures | -> `TRANSFORM_LOOP_START` |
| `TRANSFORM_LOOP_START` | deterministic control | candidate clean, limits checked, ready steps computed | -> `SELECT_NEXT_TRANSFORMATION_STEP` |
| `SELECT_NEXT_TRANSFORMATION_STEP` | decision | one dependency-ready reversible step with oracle | step exists -> `APPLY_TRANSFORMATION_STEP`; no steps remain -> `CHECK_TRANSFORM_COMPLETION` |
| `APPLY_TRANSFORMATION_STEP` | action | bounded structural/API/dependency/config diff | -> `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY` |
| `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY` | independent verification | build, invariant and compatibility evidence | all pass -> `ACCEPT_TRANSFORMATION_STEP`; any fail -> `ROLLBACK_AND_DIAGNOSE` |
| `ACCEPT_TRANSFORMATION_STEP` | deterministic state | candidate promoted and step verified | -> `UPDATE_TRANSFORM_STATE` |
| `ROLLBACK_AND_DIAGNOSE` | deterministic action + decision | accepted revision restored and failure classified | build/dependency -> `FIX_BUILD_AND_DEPENDENCIES`; behavior drift -> `REVISE_TRANSFORMATION_PLAN`; semantic compatibility -> `FIX_SEMANTIC_INCOMPATIBILITY` |
| `FIX_BUILD_AND_DEPENDENCIES` | action | minimal build/dependency correction tied to target | corrected candidate ready -> `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`; fix requires a new accepted step -> `TRANSFORM_LOOP_START` |
| `REVISE_TRANSFORMATION_PLAN` | decision | smaller/reordered steps preserving invariants | -> `TRANSFORM_LOOP_START` |
| `FIX_SEMANTIC_INCOMPATIBILITY` | action | explicit adapter/shim/API correction | corrected candidate ready -> `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY`; obligation changes plan -> `TRANSFORM_LOOP_START` |
| `UPDATE_TRANSFORM_STATE` | deterministic state | accepted steps, matrix and deferred cleanup | -> `CHECK_TRANSFORM_COMPLETION` |
| `CHECK_TRANSFORM_COMPLETION` | decision | all target obligations/invariants evaluated | all satisfied -> `TRANSFORM_FINAL_VALIDATION`; type mismatch -> `ROUTE_TASK`; otherwise -> `TRANSFORM_LOOP_START` |
| `TRANSFORM_FINAL_VALIDATION` | independent verification | full clean build/behavior/compatibility suite | pass -> `TRANSFORM_COMPLETE`; fail -> `TRANSFORM_LOOP_START` |
| `TRANSFORM_COMPLETE` | deterministic state | candidate-complete accepted revision | -> `PHASE_3_FINALIZE` |

## Baseline policy

Capture pre-existing failures before changes and never call them regressions. Store exact revision, commands and environment. Baselines become stale after dependency/environment changes and must be recaptured explicitly.

## Rollback policy

Never stack a fix on an unaccepted candidate after a failed verification. Restore the accepted revision first, retain the failed diff as an artifact, then create a new attempt. Broad version pinning and compatibility shims require explicit target justification.
