---
name: long-horizon
description: Sustain multi-hour coding work through milestone evidence, durable checkpoints, background-job discipline, strategy resets, and context-safe recovery. Load alongside a domain playbook for long-horizon execution.
---

# Long-Horizon Playbook

Optimize for verified progress per wall-clock time, not model turn count.

## Operating Rhythm

1. Establish an executable baseline and record expensive command durations.
2. Keep one advisory global plan in your reasoning. There is no controller work
   graph in long-horizon mode; deliverables and algorithms are internal branches,
   not serial gates.
3. Create a valid scoreable baseline for every required deliverable before
   spending extended time on any one branch.
4. Work in an episode that ends at a verification, checkpoint, or safe handoff boundary.
5. Promote a checkpoint only when its evidence matches the exact workspace revision.
6. On failure, preserve the signature and change strategy; never stop because attempts accumulated.
7. Reassess remaining time before launching expensive builds or experiments.

Reuse current-revision observations. Do not reread an already observed file or
repeat an equivalent inspection unless the prior result was truncated and the
next read targets a specific unseen range.

Bundle a known post-mutation check with its edit in one batch whenever possible.
The controller also performs lightweight syntax checks for supported source
types; use that same-turn evidence instead of spending another model call on an
equivalent check.

Keep shell actions short and inspectable. Put nontrivial Python diagnostics or
experiments in named helper files rather than large heredocs or python -c
strings. This makes syntax validation automatic, preserves instrumentation for
later iterations, and avoids wasting long-horizon turns on nested quoting.

Respect real technical dependencies, but do not turn them into controller
milestones. Periodically switch among independent branches according to observed
correctness or metric gain per wall-clock time. An aspirational score threshold
is not a reason to starve another required deliverable.

Before optimizing against a custom metric implementation or surrogate, validate
it on a known input against an independent oracle. A disagreement is a blocking
correctness bug, not an optimization result.

## Expensive Operations

Run long commands in the background only when independent work exists. Record command identifiers, poll at meaningful intervals, and terminate obsolete jobs. Avoid concurrent jobs that contend for the same build outputs, ports, caches, devices, or benchmark resources. A batch is sequential; launch independent long jobs with separate background actions rather than placing them in one batch.

Microbenchmark expensive loops before committing a material fraction of the
remaining wall time. Make progress output unbuffered and ensure timeout logs are
available through the controller's command evidence rather than guessing paths
inside the target workspace.

## Checkpoints

Engineering checkpoints must be integrated and passing. Optimization checkpoints must also record the valid metric and name important ignored artifacts explicitly so the snapshot captures them. A checkpoint is a recovery reference, not permission to overwrite unrelated user work or perform destructive rollback.

## Stagnation

Detect repeated failure signatures, identical commands, edit-revert cycles, and prose without new observations. Reset at least one of hypothesis, decomposition, tool, instrumentation, input, or verification method. There is no fixed reset or handoff limit.

## Deadline Discipline

As hardening time approaches, stop opening broad speculative branches. Consolidate the best verified state, run the highest-value integration gates, preserve artifacts, and report incomplete work precisely. Do not trade correctness for a nominal completion claim.
