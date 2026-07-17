---
name: run-end-to-end-acceptance
description: Validate the complete project against its user-facing requirements. Use only when the LightCoder controller dispatches RUN_END_TO_END_ACCEPTANCE.
---

# RUN_END_TO_END_ACCEPTANCE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Project Flow Contract`](../references/project-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- project.requirements_matrix
- project.checkpoints
- project.integration_state
- workspace

## Entry Criteria

- The controller must dispatch `RUN_END_TO_END_ACCEPTANCE` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.requirements_matrix`, `project.checkpoints`, `project.integration_state`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Start from a clean or fresh process.
2. Run all required end-to-end scenarios and required build/package checks.
3. Validate outputs, failure behavior, persistence, and cross-module interactions.
4. Capture each failure with the responsible requirement and observable symptom.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `project.end_to_end_results`, `project.acceptance_failures`, `project.final_evidence`.
- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash.

## Failure Handling

- A timeout, missing dependency, flaky measurement, or unavailable service is inconclusive until classified.
- Never repair the candidate inside a verifier attempt; route the evidence back to an action or diagnosis node.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: pass -> `PROJECT_COMPLETE`; fail -> `MAP_FAILURE_TO_MILESTONE`
- The proposed route is one of: `PROJECT_COMPLETE`, `MAP_FAILURE_TO_MILESTONE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.end_to_end_results
- project.acceptance_failures
- project.final_evidence

## Routes

- `PROJECT_COMPLETE`
- `MAP_FAILURE_TO_MILESTONE`

## Constraints

- Do not substitute unit-test success for end-to-end acceptance.
