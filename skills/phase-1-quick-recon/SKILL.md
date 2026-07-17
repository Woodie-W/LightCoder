---
name: phase-1-quick-recon
description: Understand the task, repository, target, and likely deliverable in one compact reconnaissance pass. Use only when the LightCoder controller dispatches PHASE_1_QUICK_RECON.
---

# PHASE_1_QUICK_RECON

<!-- runtime-contract:start -->
## Runtime Contract

- Node kind: `decision`
- Execution mode: `tool_agent`
- Read [`Node Runtime Contract`](../references/node-runtime-contract.md) before execution.
- Read [`Shared State Contract`](../references/state-contract.md) before producing state updates.
- Read [`Orchestration Flow Contract`](../references/orchestration-flow.md) for route guards, evidence, completion, and anti-loop rules.
- Execute only this node. Return one structured `NodeResult`; the deterministic controller validates and commits it.
<!-- runtime-contract:end -->

## Input State

- task.user_task
- workspace.root
- external_run_config

## Entry Criteria

- The controller must dispatch `PHASE_1_QUICK_RECON` in the `orchestration` flow with a unique attempt id.
- Resolve the declared inputs before work begins: `task.user_task`, `workspace.root`, `external_run_config`.
- Resolve every cited evidence id and compare viable alternatives before selecting one outcome.
- Separate confirmed facts, inferences, and unknowns; keep the decision scoped to this node.
- If a required input is absent, classify it as derivable, optional, stale, or blocking; never fill it with an unsupported assumption.

## Procedure

1. Parse the task text and any explicit commands, paths, constraints, and expected outputs.
2. Confirm the working directory and repository root; identify the main language, build system, and top-level entry points.
3. Read README/build configuration plus only the files most directly related to the task; keep this in one continuous context whenever practical.
4. For a very large repository, write only a compact project map: major modules, key entry points, test/build locations, up to five task-relevant areas, and up to three unknowns.
5. Produce a concise TaskProfile with primary flow, scope, oracle, risk flags, confidence, and evidence.

## Evidence And Artifacts

- Record the selected value, rejected viable alternatives, decisive evidence ids, and any remaining uncertainty.
- A decision without new workspace effects should not create command evidence or change accepted revision.
- Proposed state updates are limited to: `task_profile`, `recon_brief`, `workspace.repo_root`, `workspace.entry_points`, `workspace.build_system`.
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
- Route guard applied: profile schema valid -> `ROUTE_TASK`
- The proposed route is one of: `ROUTE_TASK`.
- `progress.made_progress` is true only when the attempt added evidence, resolved an item, falsified a hypothesis, narrowed scope, or accepted a checkpoint.

## State Updates

- task_profile
- recon_brief
- workspace.repo_root
- workspace.entry_points
- workspace.build_system

## Routes

- `ROUTE_TASK`

## Constraints

- Do not run a baseline probe here.
- Do not create an internal budget plan.
- Do not produce a broad repository report or exhaustive file inventory.
