---
name: select-next-hypothesis
description: Choose one evidence-backed optimization hypothesis with a measurable expected effect. Use only when the LightCoder controller dispatches SELECT_NEXT_HYPOTHESIS.
---

# SELECT_NEXT_HYPOTHESIS

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Optimization Flow Contract`](../references/optimization-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- optimization.performance_baseline
- optimization.profile_data
- optimization.history
- optimization.best_result

## Entry Criteria

- The controller must dispatch `SELECT_NEXT_HYPOTHESIS` in the `optimization` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `optimization.performance_baseline`, `optimization.profile_data`, `optimization.history`, `optimization.best_result`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Identify the dominant current bottleneck or unexplored high-value mechanism.
2. State the proposed change, expected metric effect, correctness risk, and discriminating measurement.
3. Reject duplicates of prior failed hypotheses unless conditions changed.
4. Select one controlled hypothesis.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `optimization.active_hypothesis`, `optimization.expected_effect`, `optimization.hypothesis_reason`.
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
- Route guard applied: hypothesis exists -> `IMPLEMENT_CONTROLLED_CHANGE`; queue exhausted -> `CHECK_OPTIMIZATION_STOP`
- The proposed route is one of: `IMPLEMENT_CONTROLLED_CHANGE`, `CHECK_OPTIMIZATION_STOP`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- optimization.active_hypothesis
- optimization.expected_effect
- optimization.hypothesis_reason

## Routes

- `IMPLEMENT_CONTROLLED_CHANGE`
- `CHECK_OPTIMIZATION_STOP`

## Constraints

- Do not bundle independent optimizations into one experiment.
