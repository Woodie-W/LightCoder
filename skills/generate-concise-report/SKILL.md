---
name: generate-concise-report
description: Generate a short evidence-backed delivery report. Use only when the LightCoder controller dispatches GENERATE_CONCISE_REPORT.
---

# GENERATE_CONCISE_REPORT

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `delivery`
- Execution mode: `model_assisted`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Finalize Flow Contract`](../references/finalize-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task_profile
- control.subgraph_state
- final_validation.results
- final_review.diff_summary
- integrity.status

## Entry Criteria

- The controller must dispatch `GENERATE_CONCISE_REPORT` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task_profile`, `control.subgraph_state`, `final_validation.results`, `final_review.diff_summary`, `integrity.status`.
- Require a final validated revision, resolved mandatory outcomes, and no integrity blocker.
- Use only evidence-backed claims and the artifact inventory supplied by finalization.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. State the task outcome in one sentence.
2. List the essential changes and affected areas.
3. List exact validation commands and results.
4. State remaining limitations, risks, or unresolved items without speculation.
5. Reference artifacts rather than embedding large logs.

## Evidence And Artifacts

- Record delivered paths, content hashes, validated revision, evidence links, limitations, and idempotency key.
- The report must distinguish completed, partially completed, blocked, skipped, and out-of-scope work.
- Proposed state updates are limited to: `delivery.final_report`, `delivery.summary`.
- Reference large command output, diffs, benchmarks, and generated artifacts by workspace-relative path and content hash.

## Failure Handling

- If an artifact or evidence reference is stale, return to finalization instead of editing the claim around it.
- On repeated submission, verify the existing idempotency record and do not duplicate delivery side effects.
- Transport-level model/tool failures may use the runtime retry allowance; a repeatable product or command failure must leave the node with evidence.
- Preserve the current accepted revision and external limits on every failure path.

## Exit Checklist

- The node-specific procedure has stopped at this node boundary; no downstream node was executed early.
- Every claimed fact or outcome is either evidence-backed or explicitly marked unknown/inferred.
- `state_patch` touches only the declared State Updates and all referenced ids/paths resolve.
- Route guard applied: -> `SUBMIT_PATCH_OR_PROJECT`
- The proposed route is one of: `SUBMIT_PATCH_OR_PROJECT`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- delivery.final_report
- delivery.summary

## Routes

- `SUBMIT_PATCH_OR_PROJECT`

## Constraints

- Keep the report concise and do not invent metrics, tests, or claims.
