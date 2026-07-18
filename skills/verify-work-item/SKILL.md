---
name: verify-work-item
description: Verify an active work item against its recorded acceptance criteria and attach current-workspace evidence. Use only after the item enters verification mode.
---

# Verify Work Item

Treat acceptance as an evidence decision, not a confidence statement.

## Procedure

1. Read the active item's exact acceptance criteria.
2. Confirm the workspace has not changed since any evidence you intend to cite.
3. Run the narrow acceptance oracle, then the closest meaningful regression check.
4. Inspect outputs for skipped tests, stale artifacts, partial builds, flaky retries, or benchmark invalidation.
5. Cite only evidence produced against the current workspace revision.
6. Return `accept_work_item` when every mandatory criterion passes.
7. Return `reject_work_item` with a concrete failure signature and materially different next strategy when a criterion fails.

## Evidence Rules

- Successful command exit alone is insufficient if the command did not exercise the outcome.
- Run every recorded `verification_commands` entry exactly; the controller requires current-revision passing evidence for each one.
- A failing command is valuable diagnostic evidence but cannot establish acceptance.
- Generated output must be shown to originate from current sources.
- Optimization evidence must include correctness and measurement conditions.
- Transformation evidence must compare behavior at defined boundaries, not merely compile both versions.

Do not edit implementation while claiming verification. If verification reveals a required edit, reject the item and return to execution with the observed signature.

## Exit

Produce exactly one acceptance or rejection action with evidence identifiers. Never cite transcript text as evidence.
