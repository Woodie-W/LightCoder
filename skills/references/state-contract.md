# Shared State Contract

## Required top-level namespaces

- `run`: lifecycle, timestamps, terminal reason.
- `task`: immutable original user task and its content hash.
- `task_profile`: deliverables, mandatory outcomes, acceptance oracles, scope, non-goals, risks, unknowns.
- `workspace`: root, base/current/accepted revisions, dirty files, build system, entry points.
- `control`: phase, active flow/node/attempt, route history, loop and stagnation counters.
- `context`: session generation, handoff reference, estimated usage, compaction count.
- `external_run_config`: immutable limits supplied by the runner.
- `usage`: observed wall time, token/cost counters, command time and disk usage.
- `evidence_index`: immutable evidence metadata and artifact paths.
- `memory_index`: confirmed facts, decisions, failures, invalidations and supersession links.
- `skills`: immutable registry snapshot and the skill lock used by this run.
- flow-local namespace: `repair`, `feature`, `project`, `optimization`, `transform`, or `generalist`.
- final namespaces: `final_validation`, `final_review`, `integrity`, `delivery`.

## State ownership

- Control nodes may update only `control` and their declared lifecycle fields.
- Decision nodes write selections, classifications, reasons, and completion candidates.
- Action nodes write candidate revisions, diffs, artifacts, and execution observations.
- Verification nodes append immutable verification records and evidence ids.
- State nodes merge verified facts and advance work-item status.
- Delivery nodes write reports and delivery references, never verification outcomes.

## Invariants

1. `workspace.accepted_revision` changes only after a passing verification.
2. A work item cannot become verified without a passing evidence id at the same revision.
3. An old failure remains in history after a later pass.
4. `control.candidate_complete` does not imply `run.status=completed`.
5. Only `END` can write completed, after final validation and integrity checks pass.
6. External limits and original user task are immutable.
7. All file paths stored in state are workspace-relative unless explicitly external and read-only.
8. State snapshots are atomically replaced and use monotonic `revision` values.

## Memory quality

- `confirmed`: directly supported by evidence.
- `inferred`: supported indirectly and must retain uncertainty.
- `hypothesis`: flow-local, falsifiable, never treated as a fact.
- `superseded`: retained for history but not injected into new sessions.
- `expired`: invalid because its revision, dependency, environment, or time condition changed.

Skills are versioned static procedures. Runtime memories must never rewrite a skill automatically.
