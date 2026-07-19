# State Machine

## Runtime Envelope

Every transition is wrapped by the same deterministic protocol:

```text
load state
-> acquire run lease
-> recover interrupted command metadata
-> check external deadline and resources
-> build bounded context
-> invoke the single agent
-> validate proposed action
-> execute tool or apply state mutation
-> append evidence/event
-> atomically commit state
-> rotate context when required
-> release or renew lease
```

No skill or model response can bypass this envelope.

Transient model failures schedule a persisted exponential backoff capped at five
minutes per wait. The retry count never terminates the run, and deadline checks run
before retry gating.

## Business State Machine

```text
NEW
  -> RECON
  -> PLAN
  -> SELECT_EXECUTION_REGIME
       |- STANDARD_WORK
       `- LONG_HORIZON_WORK
  -> FINAL_VERIFY
  -> DELIVER
  -> COMPLETED
```

`WAITING`, `PAUSED_LIMIT`, `FAILED_INFRA`, and `CANCELLED` are run statuses, not
business phases.

## Recon And Plan

The model proposes a `TaskProfile`; the controller validates its enum values and
required fields. Routing is based on observable properties such as estimated
horizon, validation cost, milestone count, expensive experiments, and the need to
preserve a best-so-far artifact. Benchmark names are never route inputs.

Planning produces a work-item DAG. Each mandatory item requires:

- a stable identifier and concrete outcome;
- dependency identifiers;
- one playbook;
- an executable or inspectable acceptance oracle;
- at least one exact verification command for deterministic evidence matching;
- a mandatory/optional flag.

## Standard Work

```text
SELECT_READY_ITEM
  -> RUN_EPISODE
  -> VERIFY_ITEM
       |- pass -> ACCEPT_ITEM -> SELECT_READY_ITEM
       `- fail -> DIAGNOSE_REPLAN -> SELECT_READY_ITEM
```

## Long-Horizon Work

```text
ESTABLISH_BASELINE
  -> BUILD_MILESTONES
  -> SELECT_READY_ITEM
  -> RUN_EPISODE
  -> EVALUATE_PROGRESS
       |- accepted -> PROMOTE_BEST
       |- rejected -> DIAGNOSE_REPLAN
       `- stalled  -> STRATEGY_RESET
  -> DEADLINE_GATE
       |- continue      -> SELECT_READY_ITEM
       `- hard deadline -> RESTORE_BEST_AND_STOP
  -> LONG_HORIZON_VERIFY
```

There is no controller-reserved hardening fraction. The agent enters final
verification after it has relevant passing checks; otherwise useful work may
continue until the external hard deadline.

The controller promotes a best-known deliverable only when its evidence is tied to
the exact workspace revision. Engineering tasks preserve the last integrated,
passing checkpoint. Optimization tasks preserve the best correct measured result.

## Progress And Stagnation

Progress means at least one of:

- new passing or failing evidence;
- a falsified hypothesis;
- a smaller localization set;
- an accepted work item or checkpoint;
- an improved valid metric;
- a newly confirmed external fact.

Repeated prose, repeated reads, identical failed commands, and edit/rollback cycles
without new evidence are not progress. Stagnation forces a materially different
hypothesis, decomposition, tool, input, or verification method. It never imposes a
fixed attempt or replan limit.

## Termination

A run ends only when one of these conditions holds:

- all mandatory work and final verification pass;
- an external hard deadline or resource limit is reached;
- the user or harness cancels the run;
- infrastructure is unrecoverable and no valid operation can continue.

Lack of ideas, an empty hypothesis queue, repeated failure, or a context rotation
is not a termination condition.
