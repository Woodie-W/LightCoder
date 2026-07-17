---
name: capture-build-compatibility-baseline
description: Capture the current build, dependency, runtime, and compatibility state before migration. Use only when the LightCoder controller dispatches CAPTURE_BUILD_COMPATIBILITY_BASELINE.
---

# CAPTURE_BUILD_COMPATIBILITY_BASELINE

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

- transform.target
- transform.compatibility_obligations
- workspace

## Entry Criteria

- The controller must dispatch `CAPTURE_BUILD_COMPATIBILITY_BASELINE` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.target`, `transform.compatibility_obligations`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Record source and target versions plus dependency manifests.
2. Run the current supported build/test path and capture existing failures.
3. Inventory deprecated APIs, build plugins, configuration, generated assets, and runtime assumptions relevant to the migration.
4. Define target build and compatibility checks.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `transform.build_baseline`, `transform.compatibility_matrix`, `transform.deprecated_items`, `transform.baseline_revision`.
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
- Route guard applied: -> `TRANSFORM_LOOP_START`
- The proposed route is one of: `TRANSFORM_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.build_baseline
- transform.compatibility_matrix
- transform.deprecated_items
- transform.baseline_revision

## Routes

- `TRANSFORM_LOOP_START`

## Constraints

- Do not upgrade dependencies during baseline capture.
