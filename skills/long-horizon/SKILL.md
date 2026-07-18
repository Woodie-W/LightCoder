---
name: long-horizon
description: Sustain multi-hour coding work through milestone evidence, durable checkpoints, background-job discipline, strategy resets, and context-safe recovery. Load alongside a domain playbook for long-horizon execution.
---

# Long-Horizon Playbook

Optimize for verified progress per wall-clock time, not model turn count.

## Operating Rhythm

1. Establish an executable baseline and record expensive command durations.
2. Select one dependency-ready milestone with a concrete oracle.
3. Work in an episode that ends at a verification, checkpoint, or safe handoff boundary.
4. Promote a checkpoint only when its evidence matches the exact workspace revision.
5. On failure, preserve the signature and change strategy; never stop because attempts accumulated.
6. Reassess remaining time before launching expensive builds or experiments.

## Expensive Operations

Run long commands in the background only when independent work exists. Record command identifiers, poll at meaningful intervals, and terminate obsolete jobs. Avoid concurrent jobs that contend for the same build outputs, ports, caches, devices, or benchmark resources.

## Checkpoints

Engineering checkpoints must be integrated and passing. Optimization checkpoints must also record the valid metric and name important ignored artifacts explicitly so the snapshot captures them. A checkpoint is a recovery reference, not permission to overwrite unrelated user work or perform destructive rollback.

## Stagnation

Detect repeated failure signatures, identical commands, edit-revert cycles, and prose without new observations. Reset at least one of hypothesis, decomposition, tool, instrumentation, input, or verification method. There is no fixed reset or handoff limit.

## Deadline Discipline

As hardening time approaches, stop opening broad speculative branches. Consolidate the best verified state, run the highest-value integration gates, preserve artifacts, and report incomplete work precisely. Do not trade correctness for a nominal completion claim.
