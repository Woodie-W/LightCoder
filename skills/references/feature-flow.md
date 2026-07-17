# Feature Flow Contract

## State

Maintain a feature contract, acceptance items, dependency ordering, compatibility obligations, active item, vertical increments, modified interfaces, integration state, regression evidence, and completion matrix.

Each acceptance item contains observable behavior, mandatory flag, oracle, dependencies, status, evidence ids, and owning increment.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_FEATURE_STATE` | deterministic state | contract and acceptance matrix | -> `FEATURE_LOOP_START` |
| `FEATURE_LOOP_START` | deterministic control | limits checked and ready items computed | -> `SELECT_NEXT_ACCEPTANCE_ITEM` |
| `SELECT_NEXT_ACCEPTANCE_ITEM` | decision | one ready mandatory item, or highest-value optional item after mandatory items | -> `PLAN_VERTICAL_INCREMENT` |
| `PLAN_VERTICAL_INCREMENT` | decision | smallest end-to-end slice, files/interfaces/tests, local oracle | feasible bounded slice -> `IMPLEMENT_INCREMENT` |
| `IMPLEMENT_INCREMENT` | action | runnable candidate increment and diff | -> `VERIFY_ACCEPTANCE_AND_REGRESSION` |
| `VERIFY_ACCEPTANCE_AND_REGRESSION` | independent verification | acceptance, integration and regression results | all required checks pass -> `UPDATE_FEATURE_STATE`; contract ambiguity/contradiction -> `REVISE_FEATURE_CONTRACT`; implementation/boundary failure -> `DIAGNOSE_FEATURE_GAP` |
| `REVISE_FEATURE_CONTRACT` | decision | clarified contract with provenance and unchanged user constraints | contract remains feature-scale -> `FEATURE_LOOP_START`; task type changed -> `ROUTE_TASK` |
| `DIAGNOSE_FEATURE_GAP` | decision | classified local/interface/integration/environment gap and next fix | small local correction -> `IMPLEMENT_INCREMENT`; slice/design gap -> `PLAN_VERTICAL_INCREMENT`; contract gap -> `REVISE_FEATURE_CONTRACT` |
| `UPDATE_FEATURE_STATE` | deterministic state | verified item, accepted revision, updated compatibility matrix | -> `CHECK_FEATURE_COMPLETION` |
| `CHECK_FEATURE_COMPLETION` | decision | all mandatory rows and integration oracle evaluated | all pass -> `FEATURE_COMPLETE`; project-scale/type mismatch -> `ROUTE_TASK`; otherwise -> `FEATURE_LOOP_START` |
| `FEATURE_COMPLETE` | deterministic state | candidate-complete checkpoint | -> `PHASE_3_FINALIZE` |

## Contract revision policy

The agent may clarify ambiguous implementation details but may not silently weaken user-visible acceptance. Every revision records the old clause, new clause, reason, and user/evidence source. If ambiguity changes scope materially and cannot be resolved from the repository, pause for user input.

## Completion oracle

All mandatory acceptance items pass at the same revision; integration and relevant regressions pass; compatibility obligations are met or explicitly accepted; no unresolved contract unknown blocks observable behavior.
