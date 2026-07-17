---
name: diagnose-feature-gap
description: Locate why a feature increment failed acceptance or integration. Use only when the LightCoder controller dispatches DIAGNOSE_FEATURE_GAP.
---

# DIAGNOSE_FEATURE_GAP

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Feature Flow Contract`](../references/feature-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- feature.active_increment
- feature.last_verification
- feature.contract
- workspace

## Entry Criteria

- The controller must dispatch `DIAGNOSE_FEATURE_GAP` in the `feature` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `feature.active_increment`, `feature.last_verification`, `feature.contract`, `workspace`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Compare expected behavior with actual output at each layer of the vertical slice.
2. Identify whether the gap is missing logic, interface mismatch, data flow, integration, or test setup.
3. Choose the smallest corrective action or replan.
4. Rollback changes that obscure the diagnosis.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `feature.gap_diagnosis`, `feature.active_increment.revision`, `feature.next_action`.
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
- Route guard applied: small local correction -> `IMPLEMENT_INCREMENT`; slice/design gap -> `PLAN_VERTICAL_INCREMENT`; contract gap -> `REVISE_FEATURE_CONTRACT`
- The proposed route is one of: `IMPLEMENT_INCREMENT`, `PLAN_VERTICAL_INCREMENT`, `REVISE_FEATURE_CONTRACT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- feature.gap_diagnosis
- feature.active_increment.revision
- feature.next_action

## Routes

- `IMPLEMENT_INCREMENT`
- `PLAN_VERTICAL_INCREMENT`
- `REVISE_FEATURE_CONTRACT`

## Constraints

- Do not start a new acceptance item before resolving or abandoning the active one.
