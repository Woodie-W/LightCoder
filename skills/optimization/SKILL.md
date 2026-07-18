---
name: optimization
description: Improve a measured objective while preserving correctness through controlled experiments and best-so-far checkpoints. Load when performance, size, throughput, latency, or another quantitative metric dominates.
---

# Optimization Playbook

Establish a trustworthy baseline before optimizing. Record workload, hardware or runtime conditions, build flags, correctness gate, metric definition, variance, and exact command.

Run controlled experiments:

1. form one causal performance hypothesis;
2. change the smallest mechanism that tests it;
3. run correctness before comparing performance;
4. repeat measurements enough to distinguish signal from noise;
5. compare against the same baseline conditions;
6. promote only a correct, reproducible improvement.

Preserve a best-so-far checkpoint before risky experiments. A faster incorrect result, a metric from a different workload, or a single noisy sample is not progress. Consider compile time, memory, startup, and portability regressions when relevant to the objective.

When an experiment loses, record why it was plausible and what evidence rejected it, then change the hypothesis rather than tuning the same parameter indefinitely.
