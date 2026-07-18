# System Architecture

## Objective

LightCoder must sustain useful coding work beyond one context window while
remaining simple enough to inspect and reproduce. It therefore separates semantic
decisions from durable execution control without introducing a supervisor LLM.

```text
CLI / Benchmark Adapter
          |
Deterministic RunController
  |- StateStore
  |- DeadlineManager
  |- ContextEpisodeManager
  |- CommandSupervisor
  |- EvidenceValidator
  `- SkillRegistry
          |
Single CodingAgent
          |
ModelClient <-> Bash / Read / Write
          |
Workspace or benchmark container
```

## Components

### RunController

Owns lifecycle and transition authority. It creates and resumes runs, validates
model proposals, selects ready work, applies deadlines, commits state, and rejects
unsupported completion. It never decides how code should be implemented.

### CodingAgent

The only LLM-driven component. It profiles the task, proposes work items, edits
code, runs tools, diagnoses failures, replans, and writes handoff summaries. The
same agent can enter execution, diagnosis, or cold-review modes without becoming a
new hierarchy level.

### StateStore

Persists a canonical JSON snapshot with atomic replacement and an append-only
event/evidence log. Filesystem and command results outrank model summaries.

### ContextEpisodeManager

Builds bounded model contexts from the original objective, canonical state,
active work, selected skills, recent observations, and the prior handoff. It
rotates context at safe tool boundaries and validates every handoff against disk.

### CommandSupervisor

Executes shell commands from a validated workspace cwd, records exit status and
output, supports process-group timeouts and background processes, and validates a
persisted PID identity before polling or termination. It does not interpret
success semantically. The deployment container remains the security boundary for
arbitrary shell code.

### EvidenceValidator

Converts tool observations into immutable evidence. State transitions can cite
evidence identifiers but cannot replace or rewrite the original record.

## Two Orthogonal Routing Axes

Execution regime describes how long work is managed:

```text
standard | long_horizon
```

Playbook describes the task method:

```text
repair | feature | project | transformation | optimization | generalist
```

A long-running migration is `long_horizon + transformation`; an extended search
task is `long_horizon + optimization`. This avoids benchmark-specific routing and
avoids duplicating control logic inside every task type.

## Deliberate Non-Goals

LightCoder has no LLM supervisor, model-managed worker hierarchy, or framework
checkpointer. Lifecycle behavior belongs to deterministic components so it cannot
consume context, hallucinate state transitions, or compete with the coding policy.
