---
name: check-global-completion
description: Decide whether all task outcomes are complete or another generalist cycle is needed. Use only when the LightCoder controller dispatches CHECK_GLOBAL_COMPLETION.
---

# CHECK_GLOBAL_COMPLETION

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

- generalist.outcomes
- generalist.subgoals
- generalist.history
- task_profile

## Entry Criteria

- The controller must dispatch `CHECK_GLOBAL_COMPLETION` in the `generalist` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `generalist.outcomes`, `generalist.subgoals`, `generalist.history`, `task_profile`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Require every mandatory outcome to have evidence.
2. Check unresolved blockers, regressions, and deliverables.
3. Detect whether remaining work now belongs to a specialized flow.
4. Record the completion decision and evidence.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `generalist.completion_decision`, `generalist.completion_evidence`, `generalist.routing_signal`.
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
- Route guard applied: all pass -> `GENERALIST_COMPLETE`; specialized remainder -> `ROUTE_TASK`; otherwise -> `GENERALIST_LOOP_START`
- The proposed route is one of: `GENERALIST_COMPLETE`, `GENERALIST_LOOP_START`, `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- generalist.completion_decision
- generalist.completion_evidence
- generalist.routing_signal

## Routes

- `GENERALIST_COMPLETE`
- `GENERALIST_LOOP_START`
- `ROUTE_TASK`

## Constraints

- Do not finish because no obvious action remains; unresolved outcomes are not completion.
