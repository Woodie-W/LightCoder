# Experiment Runbook

## Purpose

Run reproducible full-system and ablation trials without adding benchmark-specific
branches to the agent runtime. Task names and evaluator details belong only in the
experiment configuration and report.

## Prepare Each Task

1. Materialize a fresh workspace from the official task image or seed commit.
2. Record the image digest, initial Git revision, public validation command, hidden
   evaluation mechanism, CPU, memory, disk, network, and wall-time limit.
3. Put `.lightcoder` state outside the submitted workspace.
4. Use the same model endpoint, model identifier, context window, and sampling
   configuration for every compared condition.
5. Verify that the evaluator cannot be modified or inspected by the agent.

## Conditions

Run at least these conditions:

| Condition | CLI configuration | Question |
|---|---|---|
| Full | no ablation flag | Combined system result |
| Standard route | `--ablation standard-only` | Value of long-horizon routing |
| No handoff | `--ablation no-handoffs` | Value of structured context transfer |
| No best checkpoint | `--ablation no-checkpoints` | Value of best-artifact preservation |

Do not impose an attempt count. Use the same external wall deadline for all
conditions. Run at least five independent trials per task when budget permits.

## Launch

```bash
lightcoder run \
  "<official task objective>" \
  --workspace /runs/<task>/<condition>/<trial>/workspace \
  --state-root /runs/<task>/<condition>/<trial>/state \
  --wall-time 4h \
  --context-window 128000 \
  --watch \
  [--ablation <condition>]
```

Capture stdout, stderr, process exit status, environment metadata, and evaluator
output. A harness may use `--max-cycles` to yield between controller actions, but
must resume the same run rather than treating the yield as termination.

## Collect

```bash
lightcoder report RUN_ID --state-root /runs/<task>/<condition>/<trial>/state \
  > run-report.json
```

Join the report with official completion and score fields. At minimum retain:

- binary resolution and official partial/best-valid score;
- wall time and time to first valid artifact;
- model calls, invalid actions, and command duration;
- work items accepted, failure signatures, and strategy resets;
- context rotations and successful post-rotation recovery;
- best checkpoint regressions and final verification coverage.

## Analyze

Report per-task trial values plus aggregate median, dispersion, and success rate.
Inspect traces for repeated accepted work, stale-evidence rejection, repeated failed
strategies, context-recovery errors, and deadline hardening behavior. A failed task
with a correct causal trace analysis is evidence; do not replace it with an
unverified success narrative.
