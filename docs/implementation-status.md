# Implementation Status

This document maps the assignment requirements to concrete implementation and
verification. It distinguishes implemented mechanisms from experiments that need
external task workspaces and model credentials.

## Requirement Coverage

| Requirement | Implementation | Verification |
|---|---|---|
| Minimal agent loop | One `CodingAgent`, native tool calling, OpenAI-compatible client, bounded and managed shell tools | End-to-end scripted-model test |
| Autonomous multi-hour execution | Persistent `RunController`, resumable state, foreground/background commands, deadlines, retry backoff | Controller, command timeout, resume-state tests |
| Task state management | Validated task profile and dependency-aware work-item DAG | Cycle rejection, ready-selection, unlimited rejection tests |
| Context management | Bounded episode transcript, structured handoff, disk/revision validation, unlimited rotations | Handoff and milestone-rotation tests |
| Self-verification | Exact per-item verification commands, immutable evidence, current-revision matching, new final-phase command requirement | Full completion and invalid-evidence tests |
| Skill mechanism | Fourteen English, benchmark-neutral, progressively loaded skills | Manifest validation and reproducible zip test |
| Memory mechanism | Atomic state, append-only events/evidence/transcript, failure signatures, checkpoint snapshots | Revision-conflict, checkpoint, reporting tests |
| Completion control | Deterministic mandatory-item and final-evidence guards | End-to-end completion test |
| No attempt cap | Attempt counters are telemetry; failures return to ready work with a new strategy | Repeated rejection test beyond eight attempts |
| Experiment ablations | `standard-only`, `no-handoffs`, and `no-checkpoints` persisted in run config | Ablation persistence and behavior test |
| Experiment telemetry | `lightcoder report` emits time, calls, commands, failures, rotations, completion, and best checkpoint | Report assertions in controller tests |
| Optional managed evaluation | CORAL-style `eval/log/show/checkout`, agent-authored evaluator, evaluator hashes, fixed-commit grading | Evaluator success, failure, comparison, state exclusion, and restore tests |

## Implemented Boundaries

- Runtime dependencies are Python standard library only.
- No agent framework, LLM supervisor, worker hierarchy, or model-driven state
  transition authority remains.
- Runtime and skill routing do not inspect benchmark or task names.
- Managed evaluation is opt-in. Its evaluator is an editable optimization proxy;
  the hidden official benchmark evaluator remains external and authoritative.
- `read`, `write`, cwd, runtime metadata, and explicit protected paths are policy
  checked. Arbitrary `bash` commands rely on the surrounding container or OS user
  boundary.
- Checkpoints preserve changed files and named artifacts but are not automatically
  restored over a workspace that may contain concurrent user changes.

## Verified Commands

```bash
conda run -n auto-research pytest -q
conda run -n auto-research python tools/build_coding_agent_skills.py --build-zip
conda run -n auto-research python -m pip wheel --no-build-isolation --no-deps .
```

The current suite contains 76 tests. The wheel inspection confirms that all fourteen
skills and the manifest are installed with the package.

## External Experiment Status

Official benchmark runs and measured scores are maintained by the external Harbor
experiment workspace. This repository documents the runtime and adapters; follow
the experiment runbook and keep measured results separate from proxy evaluations.
