---
name: run-integrity-check
description: Check that the result is legitimate, scoped, reproducible, and free of evaluation tampering. Use only when the LightCoder controller dispatches RUN_INTEGRITY_CHECK.
---

# RUN_INTEGRITY_CHECK

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

- final_review.diff_summary
- final_review.artifact_inventory
- final_validation.results
- task_profile

## Entry Criteria

- The controller must dispatch `RUN_INTEGRITY_CHECK` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `final_review.diff_summary`, `final_review.artifact_inventory`, `final_validation.results`, `task_profile`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Check for modified or disabled tests/evaluators, hard-coded benchmark answers, skipped checks, secret leakage, and unexpected environment changes.
2. Check that dependency and generated-file changes are necessary and reproducible.
3. Confirm the final report can be supported by recorded evidence.
4. Classify each integrity issue as removable, task-blocking, or acceptable with explanation.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `integrity.status`, `integrity.findings`, `integrity.blockers`.
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
- Route guard applied: no blocker -> `GENERATE_CONCISE_REPORT`; removable issue -> `REMOVE_INVALID_CHANGES`
- The proposed route is one of: `GENERATE_CONCISE_REPORT`, `REMOVE_INVALID_CHANGES`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- integrity.status
- integrity.findings
- integrity.blockers

## Routes

- `GENERATE_CONCISE_REPORT`
- `REMOVE_INVALID_CHANGES`

## Constraints

- Do not infer malicious intent; judge observable effects.
