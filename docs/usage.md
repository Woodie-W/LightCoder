# Usage

## Environment

```bash
conda activate auto-research
python -m pip install --no-build-isolation -e '.[dev]'
```

```bash
export LIGHTCODER_BASE_URL="https://api.deepseek.com/v1"
export LIGHTCODER_MODEL="deepseek-v4-pro"
export LIGHTCODER_API_KEY="$DEEPSEEK_API_KEY"
```

Any OpenAI-compatible chat-completions endpoint can be used.

## Start A Run

```bash
lightcoder run \
  "Implement and verify the requested system" \
  --workspace /path/to/project \
  --state-root /path/to/runtime-state \
  --wall-time 4h \
  --watch
```

## Resume

```bash
lightcoder resume RUN_ID --state-root /path/to/runtime-state --watch
```

## Inspect State

```bash
lightcoder status RUN_ID --state-root /path/to/runtime-state
lightcoder report RUN_ID --state-root /path/to/runtime-state
lightcoder cancel RUN_ID --state-root /path/to/runtime-state
```

## Runtime Files

By default state is stored under `.lightcoder/runs/<run_id>/`. Benchmark adapters
should configure an external state root so metadata does not enter the submitted
workspace.

`--max-cycles N` yields control after N cycles without changing the run to a
terminal status. It is useful for harness scheduling and tests, not as an attempt
limit.

For controlled mechanism ablations, add one or more of `--ablation standard-only`,
`--ablation no-handoffs`, and `--ablation no-checkpoints` when creating the run.
The selected condition is persisted and shown by `lightcoder report`.

## Safety

LightCoder is intended for isolated repositories or benchmark containers. `bash`
can execute arbitrary project commands. Use container boundaries and protected-path
policies for untrusted tasks.
