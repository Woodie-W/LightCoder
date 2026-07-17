---
name: run-clean-environment-validation
description: Reproduce the final result from a clean state using the task-appropriate oracle. Use only when the LightCoder controller dispatches RUN_CLEAN_ENVIRONMENT_VALIDATION.
---

# RUN_CLEAN_ENVIRONMENT_VALIDATION

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Finalize Flow Contract`](../references/finalize-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- workspace.accepted_revision
- task_profile
- workspace
- control.subgraph_state

## Entry Criteria

- The controller must dispatch `RUN_CLEAN_ENVIRONMENT_VALIDATION` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `workspace.accepted_revision`, `task_profile`, `workspace`, `control.subgraph_state`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Create or reset to a clean checkout/environment permitted by the runner.
2. Apply only the accepted patch or project artifacts.
3. Install/build using documented commands and run the required target, regression, acceptance, compatibility, or performance checks.
4. Capture deterministic commands, outputs, and failure classification.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `final_validation.clean_run`, `final_validation.results`, `final_validation.failure_class`, `final_validation.artifacts`.
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
- Route guard applied: pass -> `INSPECT_FINAL_DIFF_AND_ARTIFACTS`; fail/inconclusive -> `ROUTE_FAILURE_BACK`
- The proposed route is one of: `INSPECT_FINAL_DIFF_AND_ARTIFACTS`, `ROUTE_FAILURE_BACK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- final_validation.clean_run
- final_validation.results
- final_validation.failure_class
- final_validation.artifacts

## Routes

- `INSPECT_FINAL_DIFF_AND_ARTIFACTS`
- `ROUTE_FAILURE_BACK`

## Constraints

- Do not rely on caches or untracked files from Phase 2.
