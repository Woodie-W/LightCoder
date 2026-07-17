---
name: initialize-transform-state
description: Initialize a behavior-preserving refactor or compatibility migration state. Use only when the LightCoder controller dispatches INITIALIZE_TRANSFORM_STATE.
---

# INITIALIZE_TRANSFORM_STATE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Transform Flow Contract`](../references/transform-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task_profile
- recon_brief
- workspace

## Entry Criteria

- The controller must dispatch `INITIALIZE_TRANSFORM_STATE` in the `transform` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Classify the transform subtype as refactor, migration, or mixed.
2. Extract target structure/version, preserved behavior, public compatibility obligations, and prohibited changes.
3. Initialize steps, accepted revisions, regressions, and compatibility risks.
4. Choose the appropriate baseline-capture node.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `transform.subtype`, `transform.target`, `transform.invariants`, `transform.compatibility_obligations`, `transform.steps`.
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
- Route guard applied: refactor -> `CAPTURE_BEHAVIOR_BASELINE`; migration -> `CAPTURE_BUILD_COMPATIBILITY_BASELINE`
- The proposed route is one of: `CAPTURE_BEHAVIOR_BASELINE`, `CAPTURE_BUILD_COMPATIBILITY_BASELINE`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- transform.subtype
- transform.target
- transform.invariants
- transform.compatibility_obligations
- transform.steps

## Routes

- `CAPTURE_BEHAVIOR_BASELINE`
- `CAPTURE_BUILD_COMPATIBILITY_BASELINE`

## Constraints

- Do not begin transformation before the preservation oracle is explicit.
