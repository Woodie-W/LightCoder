---
name: localize-relevant-code
description: Narrow the failure to the smallest plausible execution path and code region. Use only when the LightCoder controller dispatches LOCALIZE_RELEVANT_CODE.
---

# LOCALIZE_RELEVANT_CODE

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `action`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Repair Flow Contract`](../references/repair-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- repair.failure_signature
- repair.reproduction
- recon_brief
- workspace

## Entry Criteria

- The controller must dispatch `LOCALIZE_RELEVANT_CODE` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `repair.failure_signature`, `repair.reproduction`, `recon_brief`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Use stack traces, failing assertions, symbols, configuration keys, and targeted search to identify candidate files.
2. Trace callers, data flow, and relevant tests only far enough to explain the failing path.
3. Rank candidate locations with evidence and identify the next discriminating inspection or test.
4. Record ruled-out areas to prevent repeated search.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `repair.localization.candidates`, `repair.localization.execution_path`, `repair.localization.ruled_out`, `repair.evidence`.
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
- Route guard applied: causal path sufficiently bounded -> `FORM_ROOT_CAUSE_HYPOTHESIS`; no narrowing after allowed probes -> `REPLAN_REPAIR`
- The proposed route is one of: `FORM_ROOT_CAUSE_HYPOTHESIS`, `REPLAN_REPAIR`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.localization.candidates
- repair.localization.execution_path
- repair.localization.ruled_out
- repair.evidence

## Routes

- `FORM_ROOT_CAUSE_HYPOTHESIS`
- `REPLAN_REPAIR`

## Constraints

- Do not read the whole repository or edit code in this node.
