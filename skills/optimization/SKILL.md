---
name: optimization
description: Improve a measured objective while preserving correctness through controlled experiments and best-so-far checkpoints. Load when performance, size, throughput, latency, or another quantitative metric dominates.
---

# Optimization Playbook

Establish a trustworthy baseline before optimizing. Record workload, hardware or runtime conditions, build flags, correctness gate, metric definition, variance, and exact command.

When the objective has multiple required artifacts or datasets, establish a
valid baseline for all of them first. Keep them as branches of one optimization
objective and revisit each branch based on measured improvement per wall-clock
time; do not require one branch to hit an aspirational target before touching
another independent branch.

If you implement the metric or an incremental approximation yourself, compare it
against an independent oracle on the same artifact before trusting any result.
Do not promote, tune, or report a candidate while the two disagree.

Run controlled experiments:

1. form one causal performance hypothesis;
2. change the smallest mechanism that tests it;
3. run correctness before comparing performance;
4. repeat measurements enough to distinguish signal from noise;
5. compare against the same baseline conditions;
6. promote only a correct, reproducible improvement.

Preserve a best-so-far checkpoint before risky experiments. A faster incorrect result, a metric from a different workload, or a single noisy sample is not progress. Consider compile time, memory, startup, and portability regressions when relevant to the objective.

Treat required deliverable paths as promoted artifacts, never as experiment scratch
space. Every unverified experiment must write to a distinct candidate path. Score
that candidate with the independent oracle, compare it with the recorded
best-so-far metric, and only then atomically promote an actual improvement.
Preserve enough information to restore the prior best even if the next command
times out, crashes, or emits a malformed candidate.
After promoting any artifact, checkpoint all currently valid required
deliverables together so deadline recovery cannot restore code while omitting a
submission file.

Before launching a large search loop, microbenchmark a representative small
iteration count and estimate the full runtime. If one iteration recomputes a
whole-graph metric, replace it with a validated incremental delta before scaling
up. Use unbuffered progress output for commands that may reach a timeout.

When an experiment loses, record why it was plausible and what evidence rejected it, then change the hypothesis rather than tuning the same parameter indefinitely.
