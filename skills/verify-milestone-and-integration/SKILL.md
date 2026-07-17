---
name: verify-milestone-and-integration
description: Verify milestone behavior and integration with previously accepted work. Use only when the LightCoder controller dispatches VERIFY_MILESTONE_AND_INTEGRATION.
---

# VERIFY_MILESTONE_AND_INTEGRATION

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

- project.active_milestone
- project.active_slice
- project.integration_state
- workspace

## Entry Criteria

- The controller must dispatch `VERIFY_MILESTONE_AND_INTEGRATION` in the `project` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `project.active_milestone`, `project.active_slice`, `project.integration_state`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run milestone-specific tests.
2. Run the shortest end-to-end path that crosses new and existing modules.
3. Check interface contracts, startup/build behavior, and prior milestone regressions.
4. Classify failure as local, boundary, architecture, or environment.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `project.last_verification`, `project.milestone_results`, `project.integration_results`, `project.failure_class`.
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
- Route guard applied: pass -> `CHECKPOINT_PROJECT_STATE`; local failure -> `REPLAN_MILESTONE`; interface failure -> `REVISE_MODULE_BOUNDARIES`; architecture failure -> `REVISE_ARCHITECTURE`
- The proposed route is one of: `CHECKPOINT_PROJECT_STATE`, `REPLAN_MILESTONE`, `REVISE_MODULE_BOUNDARIES`, `REVISE_ARCHITECTURE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- project.last_verification
- project.milestone_results
- project.integration_results
- project.failure_class

## Routes

- `CHECKPOINT_PROJECT_STATE`
- `REPLAN_MILESTONE`
- `REVISE_MODULE_BOUNDARIES`
- `REVISE_ARCHITECTURE`

## Constraints

- Do not accept a milestone that works only in isolation.
