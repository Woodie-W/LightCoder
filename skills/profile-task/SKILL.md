---
name: profile-task
description: Profile a coding task from repository evidence and choose a standard or long-horizon execution regime plus one primary engineering playbook. Use only during initial reconnaissance.
---

# Profile Task

Classify the work from observable repository properties, not benchmark labels or task names.

## Procedure

1. Inspect the repository shape, build entry points, test surface, current failures, and requested outcome.
2. Estimate the smallest credible validation loop and the cost of full validation.
3. Identify whether progress can be divided into independently testable milestones.
4. Determine whether a known-good or best-performing artifact must survive later experiments.
5. Return one `profile_task` action using only allowed enum values.

Choose `long_horizon` when several of these are true:

- credible execution requires multiple integrated milestones;
- builds, tests, benchmarks, or data generation are expensive;
- the task spans languages, subsystems, or a broad compatibility surface;
- useful partial progress should be checkpointed;
- experiments may regress and require a best-so-far artifact;
- the estimated horizon is several hours.

Choose the primary playbook by the dominant uncertainty:

- `repair`: localize and remove an observed incorrect behavior;
- `feature`: add behavior under an existing architecture and contract;
- `project`: build or complete a broad system from multiple capabilities;
- `transformation`: preserve behavior while changing language, representation, or architecture;
- `optimization`: improve a measured objective while preserving correctness;
- `generalist`: mixed work without a dominant specialized pattern.

## Guardrails

- Do not infer complexity from repository size alone.
- Do not choose long-horizon merely to obtain more attempts.
- Do not encode benchmark, task, or hidden-verifier knowledge in the rationale.
- State uncertainty explicitly and ground the rationale in facts that later evidence can revise.

## Exit

Return a complete profile. Do not plan or edit files in this step.
