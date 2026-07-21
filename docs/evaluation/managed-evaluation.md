# Optional Managed Evaluation

LightCoder can expose a small CORAL-style evaluation loop without making it a
mandatory workflow for every task. Enable it with `lightcoder run
--managed-eval`. The agent receives one native `managed_eval` tool in work
phases and can ignore it when a task has no useful intermediate metric.

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
{"valid": true, "metrics": {"partial": 0.5, "passed": 5, "total": 10}, "test_points": []}
```

Metrics must be numeric. `test_points` is optional but, when present, must be a
JSON list. `valid` is optional; use it when a Candidate has completeness or
legality requirements. Only attempts that explicitly report `valid: true` are
eligible for automatic best-artifact restoration. Diagnostic output may precede
the final JSON line.

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

An already working evaluator can be adopted and submitted in one command. Plain
metric output is accepted, so no JSON rewrite is needed:

```bash
lightcoder eval --adopt evaluate.py --primary S3 -- graph1 graph2 result.align
```

This copies the script into the managed evaluator directory, records portable
workspace-relative arguments, generates `metrics.toml`, and immediately submits
the baseline. Existing file arguments outside the workspace, such as candidates
under `/tmp`, are copied to stable paths under `.lightcoder-eval-inputs/` so the
candidate commit remains reproducible. `--direction` defaults to `maximize` and
also accepts `minimize`.

The native tool supports three operations:

- `submit` performs adoption and submission in one call. Pass `script`,
  `primary`, and `arguments` when first configuring an evaluator or when the
  candidate path changes. Calls may omit them only when the previously
  configured command still points at the desired workspace candidate.
- `history` lists retained attempts with their Candidate and evaluator versions.
- `restore` restores the exact Candidate from `attempt_id`. The Git backend does
  not move `HEAD`; both backends refuse to overwrite work changed since the
  latest submission.

At final verification and the task deadline, the controller restores the best
explicitly valid attempt under the latest evaluator. If no such attempt exists,
it leaves managed-evaluation snapshots alone and falls back to any traditional
validated checkpoint. This keeps one validity gate and one version store without
making managed evaluation mandatory.

When Git is available, `eval` stages and commits the current workspace and
evaluates that fixed commit in a detached temporary worktree. If the task image
does not contain Git, LightCoder automatically uses an internal file snapshot
instead; submission, comparison, history, and restore keep the same interface.
If Git is installed but the workspace has no repository, the first explicit
`eval` initializes one. No repository or snapshot is created when the optional
mechanism is not used.

Each attempt also captures the available LightCoder run ID, model, model-call
count, context episodes, token usage, duration, complete evaluator log, metrics,
and detailed test points.

The run state and evaluation store are excluded from Candidate commits even
when the configured state root is inside the task workspace. They therefore do
not make a clean Candidate appear changed, and restoring an attempt does not
overwrite runtime metadata.

`checkout` refuses to overwrite a dirty workspace. With Git it restores the
selected commit into the index and working tree without moving `HEAD`; with the
snapshot backend it restores the captured file tree. In either case the restored
candidate can be edited and submitted as a new evaluation.

## Prompt exposure

When enabled, LightCoder provides a short capability notice at task start and a
compact attempt summary in persistent context. Evaluator writes are remembered,
including conventionally named scripts such as `evaluate.py`, `eval_align.py`,
or `network_score.py` and explicitly described evaluators with unconventional
names.

The first successful numeric evaluator run is treated as a smoke test or
reference measurement. A second evaluator result, or a later solver result that
reports metrics and a durable Candidate path, makes repeated comparison
demonstrably relevant. Before further work the next model turn exposes only
`managed_eval` and `skip_managed_eval`: the agent either records the
evaluator/candidate pair or explains why this Candidate is not reproducible or
comparable. A low score is still a useful baseline and is not by itself a reason
to skip. Skipping applies only to the current Candidate; a changed Candidate may
offer the decision again. This adaptive decision prevents accidental bypass
without forcing managed evaluation onto tasks or one-off checks. The official
benchmark grader remains outside this mechanism and authoritative.

Both foreground evaluator commands and completed `start`/`poll` jobs count.
Repeated polling of the same completed job counts once. After a successful
submission, LightCoder fingerprints the Candidate, evaluator command, working
directory, and any existing external file arguments. Ordinary rechecks of that
same Candidate are ignored; changing tracked workspace content or a referenced
external Candidate starts a new two-observation decision cycle. This avoids
duplicate attempts caused by a normal final verification while still noticing
real optimization iterations.

If a solver embeds its scorer instead of creating a separate evaluator,
LightCoder can also recognize a successful test/baseline command that reports a
simple numeric metric such as `S3: 0.104`. The same one-time reminder suggests
extracting or reusing that scoring path; it does not parse the value into a
managed result automatically.

Ordinary project tests are local checks. Agent-authored managed metrics are
optimization proxies. The benchmark's hidden official evaluator remains outside
the workspace, immutable, and authoritative.
