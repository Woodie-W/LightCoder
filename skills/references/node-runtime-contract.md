# Node Runtime Contract

Every node follows this contract. The deterministic controller, not the model, owns transitions and persistence.

## Before execution

1. Load the latest committed `state.json`; reject stale `state_revision` inputs.
2. Verify that the active node, active flow, required fields, and repository revision match the attempt.
3. Create a unique attempt with `status=running`, base revision, idempotency key, input references, and frozen external limits.
4. Load only this skill, its linked flow reference, the active work item, relevant evidence, and the latest handoff.
5. For action nodes, record the working tree and modified files before any side effect.

## During execution

- Perform only the active node's procedure and one primary work item.
- Record every command with cwd, timeout, exit code, duration, and log path.
- Store large outputs as artifacts; return summaries and references.
- Treat repository files and command results as stronger evidence than handoff or model narrative.
- Never modify external limits, hidden evaluators, or state files through shell tools.
- Stop after the node outcome is known. Do not execute the next node in the same model turn.

## Node result

Return one structured object:

```json
{
  "status": "succeeded | failed | blocked",
  "summary": "observable result, not hidden reasoning",
  "state_patch": [],
  "evidence_ids": [],
  "proposed_route": "UPPER_SNAKE_CASE_NODE",
  "route_reason": "guard and evidence that justify the route",
  "progress": {
    "made_progress": true,
    "novel_evidence": [],
    "resolved_items": []
  },
  "memory_candidates": [],
  "warnings": []
}
```

The controller must reject:

- fields outside the node's declared `State Updates`;
- a route absent from `Routes`;
- a passing verification without evidence;
- a completion decision with unresolved mandatory outcomes;
- a repository revision that differs from the verified revision.

## Evidence rules

- Evidence is immutable and has producer node, attempt id, revision, environment fingerprint, raw artifact reference, and concise result.
- A changed error is `changed_failure`, not pass.
- Infrastructure failures are `inconclusive` or `infrastructure_block`, not product failures.
- Existing failures must be distinguished from regressions using baseline evidence.
- An action node may produce observations, but only a verification node may issue a verification result.

## Routing

1. Evaluate explicit flow guards from the linked reference.
2. Require all evidence named by the guard.
3. If multiple guards match, choose the safest route: rollback/diagnose before accept, continue before complete.
4. If no guard matches, mark the attempt invalid and route to the flow's replan/diagnose node.
5. A reroute to `ROUTE_TASK` requires evidence created after the previous routing decision.

## Progress and convergence

Count progress only for new evidence, a falsified hypothesis, a smaller localization set, a verified outcome, or an accepted checkpoint. Repeated reads, repeated prose, and edit/rollback cycles are not progress.

- Retry transient model/tool transport errors with bounded backoff until recovery or an external deadline; do not impose a fixed retry-count limit.
- Do not retry deterministic command failures inside the same attempt.
- When the same failure signature repeats without new evidence, mark the flow stalled and require a materially different strategy before continuing.
- Attempt, replan, and context-handoff counters are telemetry, not termination guards.
- Never convert a limit, timeout, or lack of ideas into task completion.

## Persistence and memory

After validation, the controller atomically commits evidence, allowed state updates, attempt result, route, event, and a new state revision.

Memory candidates must include type, statement, scope, confidence, source evidence ids, and invalidation condition. Unsupported guesses stay in flow-local hypotheses. Raw logs and transcripts are referenced, not copied into memory.

## Context boundary

When the runtime requests a handoff, finish the current atomic tool operation and stop at the node boundary. Preserve current node/work item, revisions, dirty files, accepted work, exact commands and evidence, failed attempts, open risks, and the next action. A new session verifies these claims against disk before continuing.
