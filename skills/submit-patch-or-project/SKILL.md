---
name: submit-patch-or-project
description: Package and emit the final patch or project artifact after all gates pass. Use only when the LightCoder controller dispatches SUBMIT_PATCH_OR_PROJECT.
---

# SUBMIT_PATCH_OR_PROJECT

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `delivery`
- Execution mode: `deterministic_tool`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Finalize Flow Contract`](../references/finalize-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- workspace.accepted_revision
- delivery.final_report
- final_validation.results
- integrity.status
- external_run_config

## Entry Criteria

- The controller must dispatch `SUBMIT_PATCH_OR_PROJECT` in the `finalize` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `workspace.accepted_revision`, `delivery.final_report`, `final_validation.results`, `integrity.status`, `external_run_config`.
- Require a final validated revision, resolved mandatory outcomes, and no integrity blocker.
- Use only evidence-backed claims and the artifact inventory supplied by finalization.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Confirm validation passed and integrity status is clear.
2. Produce the required patch, repository state, archive, or benchmark submission format.
3. Include only permitted files and deterministic metadata.
4. Record artifact paths, checksums when useful, and submission status.

## Evidence And Artifacts

- Record delivered paths, content hashes, validated revision, evidence links, limitations, and idempotency key.
- The report must distinguish completed, partially completed, blocked, skipped, and out-of-scope work.
- Proposed state updates are limited to: `delivery.status`, `delivery.final_artifacts`, `delivery.submission_metadata`.
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
- Route guard applied: -> `END`
- The proposed route is one of: `END`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- delivery.status
- delivery.final_artifacts
- delivery.submission_metadata

## Routes

- `END`

## Constraints

- Do not submit if clean validation or integrity checks failed.
