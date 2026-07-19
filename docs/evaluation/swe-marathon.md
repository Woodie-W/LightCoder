# SWE-Marathon Evaluation

## Role Of The Benchmark

SWE-Marathon validates the generic `long_horizon` execution regime. Runtime code,
prompts, routes, and skills must not check `SWE-Marathon` or any task identifier.

The selected tasks cover complementary work shapes:

| Task | Regime | Primary playbook | Primary persistent object |
|---|---|---|---|
| rust-java-lsp | long_horizon | project | capability coverage matrix |
| ruby-rust-port | long_horizon | transformation | parity gate matrix |
| vliw-kernel-optimization | long_horizon | optimization | correct best kernel and cycle score |
| find-network-alignments | long_horizon | optimization | valid best alignments and scores |

## Fair Comparison

Compare LightCoder and baseline agents with the same model, task image, wall-clock
limit, CPU/memory, network policy, and number of trials. Run at least five seeds per
task when cost permits.

## Metrics

Primary metrics:

- binary task resolution;
- official partial score;
- best valid score reached before deadline.

System metrics:

- time and tokens to first valid artifact;
- context rotations and recovery success;
- accepted progress per hour;
- repeated-failure and no-progress time;
- best-artifact regression count;
- validation coverage and time spent in explicit final verification.

## Ablations

At minimum compare:

1. Full LightCoder.
2. No durable state, transcript-only continuation.
3. Summary-only compaction without disk-grounded handoff validation.
4. No long-horizon route, using only the standard loop.
5. No best-artifact promotion or hard-deadline best restoration.

Implemented experiment flags cover three mechanism-level controls:

```text
--ablation standard-only
--ablation no-handoffs
--ablation no-checkpoints
```

Flags are persisted in run state and emitted by `lightcoder report`, so a resumed
trial cannot silently change its experimental condition. Additional transcript-only
or deadline-policy ablations should be implemented only when that experiment is
scheduled; they are not simulated by relabeling a normal run.

## Task-Neutral Interpretation

The four selected tasks alone do not establish universal coding-agent superiority.
Report a short/medium coding suite alongside SWE-Marathon to measure routing overhead
and verify that long-horizon mechanisms do not regress bounded tasks.
