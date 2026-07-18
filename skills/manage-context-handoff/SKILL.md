---
name: manage-context-handoff
description: End a context episode at a safe boundary and preserve unresolved work in a validated state-grounded handoff. Use near context limits, after milestones, or when an operator requests rotation.
---

# Manage Context Handoff

The durable state and repository are authoritative. The handoff exists to preserve unresolved reasoning, not to replace either.

## Before Rotation

1. Finish or terminate the current atomic tool operation.
2. Poll relevant background commands and record their identifiers and status.
3. Recheck repository status and the current workspace revision.
4. Ensure accepted work cites valid evidence and pending edits are not described as accepted.
5. Identify failed strategies, open risks, and one concrete next action.
6. Return `rotate_context` with a precise reason and next action.

## Handoff Content

Preserve:

- active outcome and acceptance oracle;
- decisions whose rationale is not obvious from code;
- exact commands needed to reproduce important evidence;
- failed approaches and the evidence that falsified them;
- best checkpoint or artifact;
- external jobs still running;
- the next discriminating action.

Discard:

- conversational chronology;
- repeated source excerpts;
- speculative branches no longer supported by evidence;
- generic coding advice;
- claims that conflict with disk.

## Recovery Rule

At the start of the next episode, compare handoff revision and paths with disk. If they disagree, trust disk, record the conflict, and reconstruct the next action before editing.

There is no maximum number of handoffs.
