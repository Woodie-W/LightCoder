---
name: implement-controlled-change
description: Implement one isolated optimization candidate from the accepted best revision. Use only when the LightCoder controller dispatches IMPLEMENT_CONTROLLED_CHANGE.
---

# IMPLEMENT_CONTROLLED_CHANGE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.active_hypothesis
- optimization.best_result
- workspace

## Entry Criteria

- The controller must dispatch `IMPLEMENT_CONTROLLED_CHANGE` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.active_hypothesis`, `optimization.best_result`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Ensure the workspace matches the best accepted revision.
2. Apply only the change required by the hypothesis.
3. Record changed files, configuration, and any build step.
4. Create a reversible candidate revision.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `optimization.candidate_revision`, `optimization.candidate_diff`, `optimization.modified_files`, `workspace.current_revision`, `workspace.dirty_files`.
- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash.

## Failure Handling

- Preserve partial logs and the exact failure signature; do not silently broaden the patch after a deterministic failure.
- Restore the rollback point before abandoning a candidate when the node contract requires a clean accepted state.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: -> `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`
- The proposed route is one of: `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.candidate_revision
- optimization.candidate_diff
- optimization.modified_files
- workspace.current_revision
- workspace.dirty_files

## Routes

- `RUN_CORRECTNESS_AND_PERFORMANCE_TESTS`

## Constraints

- Do not alter the benchmark, input workload, scoring code, or correctness oracle.
