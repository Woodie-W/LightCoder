# Persistent State Schema

## Workspace Layout

Runtime metadata is stored outside the target repository whenever the harness
allows it, so agent bookkeeping cannot pollute the submitted patch.

```text
.lightcoder/
  runs/<run_id>/
    state.json
    events.jsonl
    evidence.jsonl
    transcript.jsonl
    handoffs/<generation>.json
    commands/<command_id>.log
    checkpoints/<checkpoint_id>.json
```

## Root State

```json
{
  "schema_version": 1,
  "revision": 0,
  "run_id": "run-...",
  "objective": "...",
  "workspace": "/workspace",
  "status": "running",
  "phase": "recon",
  "profile": {},
  "work_items": [],
  "active_work_item_id": null,
  "evidence_ids": [],
  "episodes": [],
  "best_checkpoint_id": null,
  "deadline": {},
  "runtime_config": {"ablations": []},
  "counters": {},
  "retry_at": "",
  "final": {}
}
```

## Task Profile

```json
{
  "execution_regime": "standard",
  "primary_playbook": "generalist",
  "estimated_horizon": "short",
  "validation_cost": "low",
  "supports_partial_progress": true,
  "requires_best_artifact": false,
  "rationale": "..."
}
```

Allowed horizons are `short`, `medium`, and `multi_hour`. The profile is a model
proposal accepted only after schema validation.

## Work Item

```json
{
  "id": "W1",
  "title": "...",
  "description": "...",
  "kind": "capability",
  "playbook": "project",
  "status": "pending",
  "dependencies": [],
  "mandatory": true,
  "acceptance": ["command or concrete observable"],
  "verification_commands": ["exact shell command"],
  "evidence_ids": [],
  "failure_signatures": [],
  "attempt_count": 0
}
```

Work status transitions are:

```text
pending -> ready -> running -> verifying -> accepted
                              `-> rejected -> ready
                              `-> blocked
```

Attempt counts are telemetry and never guards.

## Evidence

Evidence is immutable and includes:

```json
{
  "id": "ev-...",
  "kind": "command",
  "created_at": "...",
  "work_item_id": "W1",
  "workspace_revision": "sha256:...",
  "command": "pytest ...",
  "cwd": ".",
  "exit_code": 0,
  "duration_seconds": 1.2,
  "summary": "...",
  "raw_log": "commands/cmd-....log"
}
```

Claims, hypotheses, summaries, and tool observations use different evidence kinds.
Only observations can satisfy executable acceptance guards.

Every mandatory work item has at least one exact `verification_commands` entry.
Acceptance requires current-revision exit-code-zero evidence for every entry. Final
verification evidence must be created after the run enters `final_verify`.

## Context Episode

An episode records generation, token estimate, start/end reason, active work item,
handoff path, and transcript offsets. The episode counter has no maximum.

## Checkpoint

A checkpoint records workspace fingerprint, Git base revision, changed files,
accepted work, validation evidence, metric name/value, restore notes, and a tar.gz
snapshot of current changed files plus explicitly named artifacts. Promotion is
atomic with the state revision that references it. Snapshots preserve best-known
work but are never restored automatically over a possibly user-modified workspace.

## Atomic Commit

Writers acquire a run lease, verify the expected state revision, write a temporary
JSON file, fsync, and replace `state.json`. Events and evidence are appended before
the state references their identifiers. Recovery ignores incomplete temporary files
and trusts the highest complete state revision.
