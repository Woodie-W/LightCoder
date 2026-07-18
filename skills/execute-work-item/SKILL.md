---
name: execute-work-item
description: Execute one active work item through repository inspection, minimal coherent edits, and focused feedback while preserving the durable plan. Use during standard or long-horizon work before formal verification.
---

# Execute Work Item

Work only on the active outcome. Read canonical state before trusting prior prose.

## Loop

1. Recheck relevant files, repository status, and the latest tool evidence.
2. State the narrow uncertainty the next action resolves.
3. Use the cheapest discriminating read, search, build, test, or experiment.
4. Make one coherent change set that addresses the current hypothesis.
5. Run focused feedback before broad validation.
6. When the implementation is ready for its acceptance oracle, return `begin_verification`.

Use `bash` for search, patches, formatting, builds, and tests. Use `read` for bounded source inspection. Use `write` only when atomic whole-file replacement is appropriate.

## Progress Discipline

Progress is new evidence, a falsified hypothesis, a smaller localization set, an integrated capability, or an improved valid metric. Repeating a command or explanation without a changed premise is not progress.

Before a risky edit:

- understand the current diff and generated-file policy;
- identify the nearest cheap regression signal;
- preserve unrelated user changes;
- avoid destructive cleanup unless it is required and authorized.

For expensive commands, use background execution only when other useful work can continue. Poll with purpose; do not busy-wait.

## Exit

Exit by requesting verification, recording a checkpoint, rotating context at a safe boundary, or waiting for a real external event. A failed approach is not an exit from the work item.
