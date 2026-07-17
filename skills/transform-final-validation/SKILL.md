---
name: transform-final-validation
description: Validate the complete refactor or migration from a clean state. Use only when the LightCoder controller dispatches TRANSFORM_FINAL_VALIDATION.
---

# TRANSFORM_FINAL_VALIDATION

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

- transform.completion_evidence
- transform.behavior_baseline
- transform.compatibility_matrix
- transform.current_revision

## Entry Criteria

- The controller must dispatch `TRANSFORM_FINAL_VALIDATION` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `transform.completion_evidence`, `transform.behavior_baseline`, `transform.compatibility_matrix`, `transform.current_revision`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run a clean build under the required environment.
2. Run the full relevant behavior/regression suite.
3. Run public API and compatibility checks.
4. Compare final observable behavior with the preserved baseline and target requirements.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `transform.final_validation`, `transform.final_evidence`.
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
- Route guard applied: pass -> `TRANSFORM_COMPLETE`; fail -> `TRANSFORM_LOOP_START`
- The proposed route is one of: `TRANSFORM_COMPLETE`, `TRANSFORM_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.final_validation
- transform.final_evidence

## Routes

- `TRANSFORM_COMPLETE`
- `TRANSFORM_LOOP_START`

## Constraints

- Do not accept unexplained test removals, skips, or compatibility gaps.
