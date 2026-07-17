# Finalization Flow Contract

## State

Maintain candidate revision, clean-validation specification/results, artifact inventory, diff review, integrity findings, final report claims, delivery revision and final status.

## Node guards

| Node | Mode | Required result | Route guard |
| --- | --- | --- | --- |
| `RUN_CLEAN_ENVIRONMENT_VALIDATION` | independent verification | fresh environment fingerprint and all mandatory oracle results | pass -> `INSPECT_FINAL_DIFF_AND_ARTIFACTS`; fail/inconclusive -> `ROUTE_FAILURE_BACK` |
| `ROUTE_FAILURE_BACK` | decision | failure class, responsible flow/work item and evidence | repair -> `REPAIR_LOOP_START`; feature -> `FEATURE_LOOP_START`; project -> `PROJECT_LOOP_START`; performance -> `OPTIMIZATION_LOOP_START`; migration/refactor -> `TRANSFORM_LOOP_START`; unknown/mixed -> `GENERALIST_LOOP_START` |
| `INSPECT_FINAL_DIFF_AND_ARTIFACTS` | independent inspection | scoped diff, changed/generated/dependency/secret inventory | inventory acceptable -> `RUN_INTEGRITY_CHECK`; immediately removable unrelated/invalid files -> `REMOVE_INVALID_CHANGES` |
| `RUN_INTEGRITY_CHECK` | independent verification | tampering, reproducibility, scope and report-support findings | no blocker -> `GENERATE_CONCISE_REPORT`; removable issue -> `REMOVE_INVALID_CHANGES` |
| `REMOVE_INVALID_CHANGES` | action | only invalid/unrelated changes removed, intended behavior preserved | cleanup complete -> `RUN_CLEAN_ENVIRONMENT_VALIDATION`; issue belongs to implementation flow -> `ROUTE_FAILURE_BACK` |
| `GENERATE_CONCISE_REPORT` | delivery | claims linked to evidence ids; tests, artifacts, limitations and metrics | -> `SUBMIT_PATCH_OR_PROJECT` |
| `SUBMIT_PATCH_OR_PROJECT` | deterministic delivery | idempotent delivery record at validated revision | -> `END` |

`PHASE_3_FINALIZE` and `END` are described in the orchestration reference.

## Isolation

Clean validation uses a new process and, when feasible, a fresh checkout/container with dependencies installed from declared manifests. It must not reuse generated caches that are absent from a user checkout unless those caches are declared artifacts.

The final verifier receives task criteria, repository/artifacts, state and evidence index. It does not receive implementation reasoning or a prompt claiming the task is complete.

## Integrity checks

Check for disabled/modified tests, hard-coded benchmark answers, secret leakage, broad ignores, unjustified dependency changes, generated files that cannot be reproduced, scope expansion, dirty artifacts, stale reports, and revision mismatch. Judge observable effects without inferring intent.

## Completion gate

Only `END` writes completed, and only when:

1. all mandatory clean-validation records pass;
2. all mandatory outcomes reference passing evidence at the delivery revision;
3. integrity has no blocker;
4. artifact paths exist and hashes match;
5. final report claims are evidence-backed;
6. delivery is idempotently recorded.
