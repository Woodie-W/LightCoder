---
name: inspect-final-diff-and-artifacts
description: Inspect the final change set and deliverables before integrity validation. Use only when the LightCoder controller dispatches INSPECT_FINAL_DIFF_AND_ARTIFACTS.
---

# INSPECT_FINAL_DIFF_AND_ARTIFACTS

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
- final_validation.results
- workspace

## Entry Criteria

- The controller must dispatch `INSPECT_FINAL_DIFF_AND_ARTIFACTS` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `workspace.accepted_revision`, `task_profile`, `final_validation.results`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. List tracked and untracked changes relative to the required base.
2. Confirm all expected source, configuration, migration, test, and output artifacts are present.
3. Identify unrelated, generated, secret, temporary, or oversized artifacts.
4. Check that the diff matches the task scope and report any suspicious change.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `final_review.diff_summary`, `final_review.artifact_inventory`, `final_review.invalid_changes`, `final_review.scope_assessment`.
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
- Route guard applied: inventory acceptable -> `RUN_INTEGRITY_CHECK`; immediately removable unrelated/invalid files -> `REMOVE_INVALID_CHANGES`
- The proposed route is one of: `RUN_INTEGRITY_CHECK`, `REMOVE_INVALID_CHANGES`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- final_review.diff_summary
- final_review.artifact_inventory
- final_review.invalid_changes
- final_review.scope_assessment

## Routes

- `RUN_INTEGRITY_CHECK`
- `REMOVE_INVALID_CHANGES`

## Constraints

- Do not edit files unless routing to removal/repair.
