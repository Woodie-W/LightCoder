---
name: verify-acceptance-and-regression
description: Verify the active acceptance item and detect integration or compatibility regressions. Use only when the LightCoder controller dispatches VERIFY_ACCEPTANCE_AND_REGRESSION.
---

# VERIFY_ACCEPTANCE_AND_REGRESSION

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Feature Flow Contract`](../references/feature-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- feature.active_acceptance_item
- feature.active_increment
- feature.contract
- workspace

## Entry Criteria

- The controller must dispatch `VERIFY_ACCEPTANCE_AND_REGRESSION` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.active_acceptance_item`, `feature.active_increment`, `feature.contract`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the item-specific acceptance test or direct behavioral check.
2. Run nearby integration tests and relevant regressions.
3. Check interface shape, error behavior, and backward compatibility called out in the contract.
4. Classify failure as contract, implementation, integration, or environment.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `feature.last_verification`, `feature.acceptance_results`, `feature.regression_results`, `feature.failure_class`.
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
- Route guard applied: all required checks pass -> `UPDATE_FEATURE_STATE`; contract ambiguity/contradiction -> `REVISE_FEATURE_CONTRACT`; implementation/boundary failure -> `DIAGNOSE_FEATURE_GAP`
- The proposed route is one of: `UPDATE_FEATURE_STATE`, `REVISE_FEATURE_CONTRACT`, `DIAGNOSE_FEATURE_GAP`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.last_verification
- feature.acceptance_results
- feature.regression_results
- feature.failure_class

## Routes

- `UPDATE_FEATURE_STATE`
- `REVISE_FEATURE_CONTRACT`
- `DIAGNOSE_FEATURE_GAP`

## Constraints

- A partial behavior does not satisfy an acceptance item.
