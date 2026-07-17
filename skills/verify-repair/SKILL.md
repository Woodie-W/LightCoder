---
name: verify-repair
description: Determine whether the patch fixes the target failure without introducing regressions. Use only when the LightCoder controller dispatches VERIFY_REPAIR.
---

# VERIFY_REPAIR

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.current_patch
- repair.reproduction
- repair.failure_signature
- workspace

## Entry Criteria

- The controller must dispatch `VERIFY_REPAIR` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.current_patch`, `repair.reproduction`, `repair.failure_signature`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the exact reproduction or targeted test first.
2. If it passes, run the smallest relevant regression set and then the project-required suite when feasible.
3. Compare new failures with the stored failure signature.
4. Classify the result as passed, changed failure, unchanged failure, regression, or infrastructure block.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `repair.last_verification`, `repair.test_results`, `repair.new_failure_signature`, `repair.evidence`.
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
- Route guard applied: target+regression pass -> `UPDATE_REPAIR_STATE`; changed signature -> `UPDATE_FAILURE_SIGNATURE`; unchanged/regression/inconclusive -> `REPLAN_REPAIR`
- The proposed route is one of: `UPDATE_REPAIR_STATE`, `UPDATE_FAILURE_SIGNATURE`, `REPLAN_REPAIR`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.last_verification
- repair.test_results
- repair.new_failure_signature
- repair.evidence

## Routes

- `UPDATE_REPAIR_STATE`
- `UPDATE_FAILURE_SIGNATURE`
- `REPLAN_REPAIR`

## Constraints

- A changed error is progress evidence, not success.
- Do not accept skipped or disabled tests as a pass.
