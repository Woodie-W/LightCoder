# Repair Flow Contract

## State

Maintain problem statement, expected behavior, reproduction, failure signature, localization set, falsifiable hypotheses, active hypothesis, attempts, patch/diff, modified files, baseline failures, verification evidence, and best accepted revision.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `INITIALIZE_REPAIR_STATE` | deterministic state | empty attempt ledger and reported behavior | -> `REPAIR_LOOP_START` |
| `REPAIR_LOOP_START` | deterministic control | counters/limits checked, stale candidate removed | -> `SELECT_NEXT_REPAIR_ACTION` |
| `SELECT_NEXT_REPAIR_ACTION` | decision | exactly one action and evidence gap | no reproduction -> `REPRODUCE_OR_INSPECT`; broad path -> `LOCALIZE_RELEVANT_CODE`; no falsifiable cause -> `FORM_ROOT_CAUSE_HYPOTHESIS`; testable active hypothesis -> `IMPLEMENT_MINIMAL_PATCH` |
| `REPRODUCE_OR_INSPECT` | action/inspection | exact command, environment, observed/expected output | target now passes without patch -> `VERIFY_REPAIR`; reproducible signature -> `LOCALIZE_RELEVANT_CODE`; infrastructure/no viable reproduction -> `REPLAN_REPAIR` |
| `LOCALIZE_RELEVANT_CODE` | model-assisted inspection | bounded symbols/call path with evidence | causal path sufficiently bounded -> `FORM_ROOT_CAUSE_HYPOTHESIS`; no narrowing after allowed probes -> `REPLAN_REPAIR` |
| `FORM_ROOT_CAUSE_HYPOTHESIS` | decision | claim, prediction, falsifier, affected symbols | testable -> `IMPLEMENT_MINIMAL_PATCH`; path evidence insufficient -> `LOCALIZE_RELEVANT_CODE` |
| `IMPLEMENT_MINIMAL_PATCH` | action | candidate diff tied to active hypothesis and rollback point | candidate exists -> `VERIFY_REPAIR` |
| `VERIFY_REPAIR` | independent verification | exact reproduction plus relevant regression record | target+regression pass -> `UPDATE_REPAIR_STATE`; changed signature -> `UPDATE_FAILURE_SIGNATURE`; unchanged/regression/inconclusive -> `REPLAN_REPAIR` |
| `UPDATE_FAILURE_SIGNATURE` | deterministic state | immutable old signature plus new signature | causal clue present -> `FORM_ROOT_CAUSE_HYPOTHESIS`; path changed/unclear -> `LOCALIZE_RELEVANT_CODE` |
| `REPLAN_REPAIR` | decision | failed hypothesis marked, distinct next strategy | repair remains viable -> `REPAIR_LOOP_START`; new evidence changes task type -> `ROUTE_TASK` |
| `UPDATE_REPAIR_STATE` | deterministic state | attempt ledger, confirmed/rejected hypothesis, accepted revision only on pass | -> `CHECK_REPAIR_COMPLETION` |
| `CHECK_REPAIR_COMPLETION` | decision | mandatory repair oracle matrix | all pass -> `REPAIR_COMPLETE`; task type changed -> `ROUTE_TASK`; otherwise -> `REPAIR_LOOP_START` |
| `REPAIR_COMPLETE` | deterministic state | candidate-complete checkpoint and evidence references | -> `PHASE_3_FINALIZE` |

## Completion oracle

Require the original failure to be reproduced or a documented reason it cannot be, the target behavior to pass, the smallest relevant regression set to pass, no unexplained new failures, and the verified revision to equal the candidate revision. A changed exception, skipped test, disabled assertion, or manual code inspection alone is not success.

## Anti-loop policy

Normalize failure signatures. If the same signature survives repeated patch attempts without new localization evidence, forbid an identical retry and force a materially different diagnosis, experiment, decomposition, or patch strategy. Do not cap attempts or replans; a rejected hypothesis may be revisited only when new evidence explicitly reopens it.
