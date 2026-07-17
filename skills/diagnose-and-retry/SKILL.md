---
name: diagnose-and-retry
description: Diagnose a failed subgoal execution and choose a materially different retry. Use only when the LightCoder controller dispatches DIAGNOSE_AND_RETRY.
---

# DIAGNOSE_AND_RETRY

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Generalist Flow Contract`](../references/generalist-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- generalist.active_subgoal
- generalist.selected_skill
- generalist.execution_result
- generalist.last_verification

## Entry Criteria

- The controller must dispatch `DIAGNOSE_AND_RETRY` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.active_subgoal`, `generalist.selected_skill`, `generalist.execution_result`, `generalist.last_verification`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Classify the failure as tool, environment, context, implementation, or oracle mismatch.
2. Preserve useful partial artifacts and rollback harmful changes.
3. Select a corrected skill plan or a narrower reproduction.
4. Record why the retry differs from the failed attempt.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `generalist.retry_plan`, `generalist.history`, `workspace.current_revision`, `workspace.dirty_files`.
- Keep the result compact; reference existing evidence ids instead of copying logs or transcript text into state.

## Failure Handling

- If evidence is insufficient, choose a legal evidence-gathering/replan route rather than fabricate certainty.
- If candidates remain tied, prefer the smaller reversible action and record the tie.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: another skill needed -> `SELECT_SKILL`; same skill with corrected inputs -> `EXECUTE_SUBGOAL`; subgoal invalid -> `REVISE_TASK_DECOMPOSITION`
- The proposed route is one of: `SELECT_SKILL`, `EXECUTE_SUBGOAL`, `REVISE_TASK_DECOMPOSITION`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.retry_plan
- generalist.history
- workspace.current_revision
- workspace.dirty_files

## Routes

- `SELECT_SKILL`
- `EXECUTE_SUBGOAL`
- `REVISE_TASK_DECOMPOSITION`

## Constraints

- Do not repeat the identical failing action more than once without new evidence.
