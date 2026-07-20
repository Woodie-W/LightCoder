# Optional Managed Evaluation

LightCoder can expose a CORAL-style command loop without making it part of the
agent's core tool protocol. Enable it with `lightcoder run --managed-eval`. The
agent still uses its ordinary `run` tool and may ignore this mechanism when a
task has no useful intermediate metric.

## Agent-authored evaluator

The agent owns two normal workspace files:

```text
.lightcoder-eval/
├── evaluate.py
└── metrics.toml
```

`evaluate.py` runs with the submitted workspace as its current directory. Its
last non-empty stdout line must be one JSON object:

```json
{"metrics": {"partial": 0.5, "passed": 5, "total": 10}, "test_points": []}
```

Metrics must be numeric. `test_points` is optional but, when present, must be a
JSON list. Diagnostic output may precede the final JSON line.

`metrics.toml` declares the comparison contract using only Python's standard
library:

```toml
primary = "partial"
timeout_seconds = 600

[metrics.partial]
direction = "maximize"
description = "Passed public checks divided by total public checks"
```

The agent may change either file. Their content hash is the evaluator version;
results from different evaluator versions are retained but never compared as an
improvement or regression.

## Commands

```bash
lightcoder eval -m "what changed and why"
lightcoder log
lightcoder show A0001
lightcoder checkout A0001
```

`eval` stages and commits the current Git workspace, evaluates that fixed commit
in a detached temporary worktree, stores the complete log, and compares the
primary metric with the best result under the same evaluator version.
If the task workspace has no Git repository, the first explicit `eval` initializes
a local repository there. No repository is created when the optional mechanism is
not used.

Each attempt also captures the available LightCoder run ID, model, model-call
count, context episodes, token usage, duration, complete evaluator log, metrics,
and detailed test points.

`checkout` refuses to overwrite a dirty workspace. It restores the selected
commit into the index and working tree without moving `HEAD`, so a restored
candidate can be edited and submitted as a new evaluation.

## Prompt exposure

When enabled, LightCoder provides a short capability notice at task start and a
compact attempt summary in persistent context. The first ordinary test command
also receives one optional reminder. The agent is never required to submit a
managed evaluation.

Ordinary project tests are local checks. Agent-authored managed metrics are
optimization proxies. The benchmark's hidden official evaluator remains outside
the workspace, immutable, and authoritative.
