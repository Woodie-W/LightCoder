# Optimization Flow Contract

## State

Maintain correctness baseline, metric specification, measurement protocol, environment fingerprint, performance baseline distribution, hypothesis queue, candidate results, accepted best result, rejected candidates and external stop limits.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_OPTIMIZATION_STATE` | model-assisted state | frozen correctness oracle, primary metric, direction, repeats, noise/acceptance rule and baseline | -> `OPTIMIZATION_LOOP_START` |
| `OPTIMIZATION_LOOP_START` | deterministic control | environment stable, limits checked | -> `SELECT_NEXT_HYPOTHESIS` |
| `SELECT_NEXT_HYPOTHESIS` | decision | distinct falsifiable hypothesis with expected information gain | hypothesis exists -> `IMPLEMENT_CONTROLLED_CHANGE`; queue exhausted -> `CHECK_OPTIMIZATION_STOP` |
| `IMPLEMENT_CONTROLLED_CHANGE` | action | one-variable candidate diff and revision | -> `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS` |
| `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS` | independent verification | correctness results and comparable metric distribution | correct+accepted improvement -> `ACCEPT_CANDIDATE`; correct/no improvement or incorrect -> `ROLLBACK_AND_REJECT`; excessive variance -> `STABILIZE_AND_RETEST` |
| `ACCEPT_CANDIDATE` | deterministic state | verified candidate promoted to best | -> `UPDATE_EXPERIMENT_STATE` |
| `ROLLBACK_AND_REJECT` | deterministic action | workspace restored to accepted best revision, rejection reason retained | -> `UPDATE_EXPERIMENT_STATE` |
| `STABILIZE_AND_RETEST` | action/verification | variance cause controlled without changing candidate semantics | environment stabilized -> `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`; comparable measurement impossible -> `ROLLBACK_AND_REJECT` |
| `UPDATE_EXPERIMENT_STATE` | deterministic state | immutable trial row and hypothesis status | -> `CHECK_OPTIMIZATION_STOP` |
| `CHECK_OPTIMIZATION_STOP` | decision | stop reason independent of success | target unmet and external time remains -> regenerate strategy via `OPTIMIZATION_LOOP_START`; target met or true external termination -> `FINAL_PERFORMANCE_VALIDATION` |
| `FINAL_PERFORMANCE_VALIDATION` | independent verification | fresh correctness and performance run at best revision | pass -> `OPTIMIZATION_COMPLETE`; fail -> `ROLLBACK_TO_BEST_RESULT` |
| `ROLLBACK_TO_BEST_RESULT` | deterministic action | restored last fully verified best; invalidate bad result | restored best is final candidate -> `FINAL_PERFORMANCE_VALIDATION`; no valid best remains -> `OPTIMIZATION_LOOP_START` |
| `OPTIMIZATION_COMPLETE` | deterministic state | candidate-complete best result | -> `PHASE_3_FINALIZE` |

## Measurement integrity

The metric direction and acceptance threshold are frozen before candidates. Compare distributions under the same data, command, warmup, repeats and environment fingerprint. Report variance and raw samples. Secondary metrics cannot override a failed primary rule unless external config explicitly allows it.

## Stop policy

Stop only on target reached, an external hard limit, explicit cancellation, or an unrecoverable infrastructure failure. An empty hypothesis queue or repeated stagnation triggers strategy regeneration rather than termination. Reaching a limit means stopped, not successful. Always preserve and finally verify the last accepted best revision.
