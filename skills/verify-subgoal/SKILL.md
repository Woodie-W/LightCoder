---
name: verify-subgoal
description: Verify the active subgoal against its local oracle and detect a clearer task type. Use only when the LightCoder controller dispatches VERIFY_SUBGOAL.
---

# VERIFY_SUBGOAL

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `verification`
- Execution mode: `isolated_verifier`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Generalist Flow Contract`](../references/generalist-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- generalist.active_subgoal
- generalist.subgoal_oracle
- generalist.execution_result
- workspace

## Entry Criteria

- The controller must dispatch `VERIFY_SUBGOAL` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.active_subgoal`, `generalist.subgoal_oracle`, `generalist.execution_result`, `workspace`.
- Use a fresh verifier context and verify the candidate revision, oracle, and environment before running checks.
- Do not rely on the generator's success claim or hidden reasoning; inspect artifacts and executable behavior.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the narrowest reliable check for the subgoal.
2. Compare actual artifacts or behavior with the done condition.
3. Classify failure as decomposition, skill execution, environment, or task-type mismatch.
4. Identify whether evidence now supports a specialized flow.

## Evidence And Artifacts

- Create immutable evidence for each required oracle with command/probe, cwd, environment, revision, exit code, duration, summary, and raw-log path.
- Record skipped checks, pre-existing failures, changed failures, regressions, and infrastructure blocks explicitly.
- Proposed state updates are limited to: `generalist.last_verification`, `generalist.failure_class`, `generalist.routing_signal`.
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
- Route guard applied: pass -> `UPDATE_GENERALIST_STATE`; specialized flow now clear -> `ROUTE_TASK`; decomposition invalid -> `REVISE_TASK_DECOMPOSITION`; execution/environment issue -> `DIAGNOSE_AND_RETRY`
- The proposed route is one of: `UPDATE_GENERALIST_STATE`, `ROUTE_TASK`, `REVISE_TASK_DECOMPOSITION`, `DIAGNOSE_AND_RETRY`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.last_verification
- generalist.failure_class
- generalist.routing_signal

## Routes

- `UPDATE_GENERALIST_STATE`
- `ROUTE_TASK`
- `REVISE_TASK_DECOMPOSITION`
- `DIAGNOSE_AND_RETRY`

## Constraints

- Do not mark a subgoal complete from narrative confidence alone.
