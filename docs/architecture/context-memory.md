# Context And Memory

## Context Layers

Every model request is assembled from four layers:

1. Pinned: system contract, original objective, safety and completion invariants.
2. Durable: task profile, active work item, accepted work, best checkpoint, risks.
3. Working: selected skills, relevant file excerpts, recent evidence and commands.
4. Recent: a bounded tail of the current episode transcript.

The full transcript is archived but not repeatedly reinjected.

## Rotation Triggers

Rotate at a safe tool boundary when any condition holds:

- estimated prompt use leaves fewer than the configured reserve (8,000 tokens by default);
- the provider reports context exhaustion;
- a milestone finishes;
- repeated context indicates plan drift or stagnation;
- an operator explicitly requests a checkpoint.

There is no fixed maximum number of rotations.

## Handoff Protocol

```text
finish atomic tool operation
-> capture workspace fingerprint and dirty files
-> commit evidence and state
-> summarize only unresolved reasoning
-> build a structured handoff from canonical state
-> validate referenced files/evidence/checkpoints
-> start a fresh episode
-> recheck disk before taking the next action
```

The handoff contains objective, constraints, active work, accepted work, best
artifact, exact commands, failed strategies, open risks, and the next concrete
action. When summary and disk disagree, disk wins and the conflict becomes evidence.

## Memory Classes

- Run state: authoritative progress for one run.
- Evidence: immutable observations and validation results.
- Decision memory: architecture decisions with rationale and invalidation condition.
- Skill: reusable procedure independent of one run.
- Transcript: diagnostic archive, not authoritative state.

Only stable, reusable lessons become skills. Raw failures and speculative notes stay
run-local to avoid cross-task contamination.

## Compaction Quality

Compaction is evaluated by recovery behavior rather than summary fluency:

- the next episode selects the correct work item;
- accepted work is not repeated;
- failed strategies are not repeated without new evidence;
- referenced artifacts exist and match the recorded revision;
- progress rate after rotation does not collapse.
