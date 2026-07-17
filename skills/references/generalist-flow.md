# Generalist Flow Contract

## State

Maintain mandatory outcomes, subgoal DAG, local oracles, active subgoal, selected skill, execution result, verification evidence, history, blockers and routing signals.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_GENERALIST_STATE` | model-assisted state | outcome list and subgoal DAG with local oracles | -> `GENERALIST_LOOP_START` |
| `GENERALIST_LOOP_START` | deterministic control | ready subgoals and limits checked | -> `SELECT_NEXT_SUBGOAL` |
| `SELECT_NEXT_SUBGOAL` | decision | one dependency-ready mandatory subgoal | valid local oracle -> `SELECT_SKILL`; no independently verifiable subgoal -> `REVISE_TASK_DECOMPOSITION` |
| `SELECT_SKILL` | decision | minimal relevant installed skill or explicit basic-tool fallback | executable match/fallback -> `EXECUTE_SUBGOAL`; skill mismatch exposes bad subgoal -> `REVISE_TASK_DECOMPOSITION` |
| `EXECUTE_SUBGOAL` | action | bounded artifact/diff/observation for one subgoal | -> `VERIFY_SUBGOAL` |
| `VERIFY_SUBGOAL` | independent verification | local oracle result and task-type signal | pass -> `UPDATE_GENERALIST_STATE`; specialized flow now clear -> `ROUTE_TASK`; decomposition invalid -> `REVISE_TASK_DECOMPOSITION`; execution/environment issue -> `DIAGNOSE_AND_RETRY` |
| `REVISE_TASK_DECOMPOSITION` | decision | changed DAG with reason and preserved completed outcomes | mixed work remains -> `GENERALIST_LOOP_START`; specialized flow now justified -> `ROUTE_TASK` |
| `DIAGNOSE_AND_RETRY` | decision/action | classified failure and one distinct retry strategy | another skill needed -> `SELECT_SKILL`; same skill with corrected inputs -> `EXECUTE_SUBGOAL`; subgoal invalid -> `REVISE_TASK_DECOMPOSITION` |
| `UPDATE_GENERALIST_STATE` | deterministic state | verified subgoal, outcome coverage and accepted revision | -> `CHECK_GLOBAL_COMPLETION` |
| `CHECK_GLOBAL_COMPLETION` | decision | every mandatory outcome evaluated | all pass -> `GENERALIST_COMPLETE`; specialized remainder -> `ROUTE_TASK`; otherwise -> `GENERALIST_LOOP_START` |
| `GENERALIST_COMPLETE` | deterministic state | candidate-complete checkpoint | -> `PHASE_3_FINALIZE` |

## Skill selection

Select by declared trigger and task fit, not by name similarity alone. Load only the chosen skill body. If no skill fits, record `basic-tools` rather than inventing a persistent skill. Runtime memory cannot create or alter installed skills.

## Decomposition policy

Subgoals should fit one context and produce an independently checkable outcome. Split a subgoal if it has multiple unrelated deliverables, lacks a local oracle, spans too many modules to hand off safely, or repeatedly fails without narrowing evidence.

## Anti-loop policy

Repeated execution of the same subgoal/failure signature without new evidence forces a materially different decomposition, hypothesis, tool, or verification method. It does not cap attempts or pause the run. Completed subgoals may be reopened only when later evidence invalidates their oracle, and the invalidation must be recorded.
