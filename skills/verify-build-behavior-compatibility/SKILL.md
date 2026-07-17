---
name: verify-build-behavior-compatibility
description: Verify buildability, preserved behavior, and compatibility after one transformation step. Use only when the LightCoder controller dispatches VERIFY_BUILD_BEHAVIOR_COMPATIBILITY.
---

# VERIFY_BUILD_BEHAVIOR_COMPATIBILITY

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Transform Flow Contract`](../references/transform-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- transform.active_step
- transform.candidate_revision
- transform.behavior_baseline
- transform.compatibility_matrix

## Entry Criteria

- The controller must dispatch `VERIFY_BUILD_BEHAVIOR_COMPATIBILITY` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.active_step`, `transform.candidate_revision`, `transform.behavior_baseline`, `transform.compatibility_matrix`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the step-specific build or static check.
2. Run targeted equivalence/regression tests.
3. Run the relevant compatibility check for the target environment or API.
4. Classify failure as build/dependency, behavior regression, semantic compatibility, or environment.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `transform.last_verification`, `transform.build_results`, `transform.behavior_results`, `transform.compatibility_results`, `transform.failure_class`.
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
- Route guard applied: all pass -> `ACCEPT_TRANSFORMATION_STEP`; any fail -> `ROLLBACK_AND_DIAGNOSE`
- The proposed route is one of: `ACCEPT_TRANSFORMATION_STEP`, `ROLLBACK_AND_DIAGNOSE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.last_verification
- transform.build_results
- transform.behavior_results
- transform.compatibility_results
- transform.failure_class

## Routes

- `ACCEPT_TRANSFORMATION_STEP`
- `ROLLBACK_AND_DIAGNOSE`

## Constraints

- Passing build alone is not sufficient.
