---
name: initialize-repair-state
description: Create the minimum structured state needed for a repair loop. Use only when the LightCoder controller dispatches INITIALIZE_REPAIR_STATE.
---

# INITIALIZE_REPAIR_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task_profile
- recon_brief
- workspace

## Entry Criteria

- The controller must dispatch `INITIALIZE_REPAIR_STATE` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Extract the reported incorrect behavior and expected behavior.
2. Record known reproduction commands, failing tests, logs, and suspected areas without asserting a root cause.
3. Define the initial repair oracle: the exact observable change required and the minimum relevant regression surface.
4. Initialize hypotheses, attempts, modified files, and verification results as empty.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `repair.problem_statement`, `repair.expected_behavior`, `repair.reproduction`, `repair.failure_signature`, `repair.hypotheses`, `repair.attempts`.
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
- Route guard applied: -> `REPAIR_LOOP_START`
- The proposed route is one of: `REPAIR_LOOP_START`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.problem_statement
- repair.expected_behavior
- repair.reproduction
- repair.failure_signature
- repair.hypotheses
- repair.attempts

## Routes

- `REPAIR_LOOP_START`

## Constraints

- Do not modify code or mark the issue reproduced without evidence.
