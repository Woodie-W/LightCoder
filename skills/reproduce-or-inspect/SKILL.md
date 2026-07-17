---
name: reproduce-or-inspect
description: Establish a reliable failure reproduction or identify the environment condition blocking it. Use only when the LightCoder controller dispatches REPRODUCE_OR_INSPECT.
---

# REPRODUCE_OR_INSPECT

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

- task_profile
- recon_brief
- repair.reproduction
- workspace

## Entry Criteria

- The controller must dispatch `REPRODUCE_OR_INSPECT` in the `repair` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `recon_brief`, `repair.reproduction`, `workspace`.
- Require a single active work item, a known rollback point, and a matching workspace revision.
- Inspect affected files immediately before editing and keep the change within the declared task scope.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Run the narrowest supplied or discoverable command that should expose the issue.
2. Capture command, environment, exit code, relevant output, and repeatability.
3. If execution is blocked, inspect dependencies, configuration, fixtures, and build/test entry points; separate environment failure from product failure.
4. Store a reproducible command or a concise blocked-reproduction explanation.

## Evidence And Artifacts

- Record base/candidate revisions, modified files, diff artifact, commands, exit codes, side effects, and rollback instructions.
- Run only a cheap syntax/build smoke check here; authoritative acceptance belongs to the next verification node.
- Proposed state updates are limited to: `repair.reproduction`, `repair.failure_signature`, `repair.environment_findings`, `repair.evidence`.
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
- Route guard applied: target now passes without patch -> `VERIFY_REPAIR`; reproducible signature -> `LOCALIZE_RELEVANT_CODE`; infrastructure/no viable reproduction -> `REPLAN_REPAIR`
- The proposed route is one of: `VERIFY_REPAIR`, `LOCALIZE_RELEVANT_CODE`, `REPLAN_REPAIR`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- repair.reproduction
- repair.failure_signature
- repair.environment_findings
- repair.evidence

## Routes

- `VERIFY_REPAIR`
- `LOCALIZE_RELEVANT_CODE`
- `REPLAN_REPAIR`

## Constraints

- Do not repair the environment in ways that hide the target defect.
- Avoid full test suites until needed.
