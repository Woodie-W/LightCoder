# LightCoder 持久状态与证据 Schema

本文规定 Long-Running Coding Agent 的磁盘事实来源。实现可使用 dataclass/Pydantic 做类型检查，但落盘格式必须保持普通 JSON/JSONL/Markdown，便于人工检查、崩溃恢复和实验分析。

## 1. 工作区布局

```text
<workspace>/
├── .lightcoder/
│   ├── state.json                 # 当前权威快照，原子替换
│   ├── events.jsonl               # 只追加事件流
│   ├── run.lock                   # 带 owner、pid、heartbeat 的租约
│   ├── config.snapshot.json       # 冻结的外部运行配置
│   ├── skill-lock.json            # 本次运行使用的 skill hash
│   ├── attempts/<attempt-id>.json # 节点调用输入、结果与路由
│   ├── evidence/<evidence-id>.json
│   ├── logs/<evidence-id>.log
│   ├── handoffs/<session-id>.md
│   ├── memory/
│   │   ├── facts.jsonl
│   │   ├── decisions.jsonl
│   │   ├── failures.jsonl
│   │   └── index.json
│   └── reports/final.md
└── project files
```

大日志、测试输出和 transcript 不嵌入 `state.json`，只通过 content hash、相对路径和摘要引用。

## 2. 根状态

示意结构：

```json
{
  "schema_version": 1,
  "revision": 42,
  "run": {
    "run_id": "run-...",
    "status": "running",
    "created_at": "RFC3339",
    "updated_at": "RFC3339",
    "completed_at": null,
    "stop_reason": null
  },
  "task": {
    "user_task": "...",
    "original_hash": "sha256:..."
  },
  "task_profile": {
    "mandatory_outcomes": [],
    "non_goals": [],
    "risk_flags": []
  },
  "workspace": {
    "root": ".",
    "repo_root": ".",
    "base_revision": "...",
    "current_revision": "...",
    "accepted_revision": "...",
    "dirty": false,
    "build_system": [],
    "entry_points": []
  },
  "control": {
    "phase": "phase_2",
    "active_flow": "repair",
    "active_node": "VERIFY_REPAIR",
    "active_attempt_id": null,
    "candidate_complete": false,
    "route_history": [],
    "loop_counters": {},
    "stagnation_count": 0
  },
  "context": {
    "session_id": "session-...",
    "generation": 2,
    "estimated_tokens": 12000,
    "handoff_path": ".lightcoder/handoffs/session-....md",
    "compaction_count": 1
  },
  "external_run_config": {},
  "usage": {},
  "skills": {"registry": [], "lock_path": ".lightcoder/skill-lock.json"},
  "evidence_index": {},
  "memory_index": {},
  "repair": {},
  "feature": {},
  "project": {},
  "optimization": {},
  "transform": {},
  "generalist": {},
  "final_validation": {},
  "integrity": {},
  "delivery": {}
}
```

`revision` 是状态快照的单调递增版本，不是 Git revision。

## 3. 生命周期枚举

Run status：

- `new`：只创建了 run，尚未侦察。
- `running`：可继续自动调度。
- `waiting_input`：缺少不可从工具获取的用户事实。
- `waiting_external`：已启动外部工作，等待可查询结果。
- `paused`：人工或正常进程退出前已 checkpoint。
- `paused_limit`：达到外部资源限制。
- `candidate_complete`：Phase 2 完成，尚未最终复验。
- `completed`：仅 END 可写。
- `failed`：可恢复策略和路由均耗尽。
- `cancelled`：外部明确取消且完成交接。

Node attempt status：`prepared | running | succeeded | failed | interrupted | abandoned`。

Verification outcome：`pass | fail | changed_failure | regression | inconclusive | infrastructure_block`。

## 4. `TaskProfile`

```json
{
  "summary": "one paragraph",
  "kind_candidates": [
    {"flow": "repair", "confidence": 0.82, "evidence_ids": ["ev-1"]}
  ],
  "deliverables": [
    {"id": "d-1", "path_or_behavior": "...", "mandatory": true}
  ],
  "acceptance_oracles": [
    {"id": "o-1", "command": "pytest ...", "expected": "exit 0", "mandatory": true}
  ],
  "scope": ["..."],
  "non_goals": ["..."],
  "constraints": ["..."],
  "risk_flags": ["migration", "untrusted-tests"],
  "unknowns": ["..."],
  "confidence": 0.0
}
```

Oracle 可以是命令、结构检查、文件/hash、API 行为或人工条件，但必须可观察。仅写“代码质量良好”不是 oracle。

## 5. `NodeAttempt` 与 `NodeResult`

每次节点调用在执行前写 attempt 文件：

```json
{
  "attempt_id": "attempt-...",
  "node": "VERIFY_REPAIR",
  "flow": "repair",
  "status": "running",
  "started_at": "RFC3339",
  "finished_at": null,
  "state_revision_in": 41,
  "base_revision": "git-or-tree-hash",
  "idempotency_key": "run/node/work-item/generation",
  "input_refs": [],
  "tool_calls": [],
  "result": null
}
```

所有节点统一返回：

```json
{
  "status": "succeeded",
  "summary": "concise observable result",
  "state_patch": [],
  "evidence_ids": [],
  "proposed_route": "UPDATE_REPAIR_STATE",
  "route_reason": "target and regression oracles passed",
  "progress": {
    "made_progress": true,
    "novel_evidence": ["ev-9"],
    "resolved_items": ["o-1"]
  },
  "memory_candidates": [],
  "warnings": []
}
```

约束：

- `state_patch` 只能修改 manifest 为该节点声明的字段。
- `proposed_route` 必须属于 manifest 的出边；controller 再评估 guard。
- 没有 evidence 的成功只表示节点过程完成，不表示任务通过。
- 节点自由文本不能覆盖结构化字段。

## 6. Evidence

```json
{
  "evidence_id": "ev-...",
  "kind": "command",
  "producer_node": "VERIFY_REPAIR",
  "attempt_id": "attempt-...",
  "created_at": "RFC3339",
  "subject": "repair target reproduction",
  "command": "pytest tests/test_x.py::test_y -q",
  "cwd": ".",
  "exit_code": 0,
  "duration_ms": 3210,
  "result": "pass",
  "summary": "1 passed",
  "artifact_paths": [],
  "log_path": ".lightcoder/logs/ev-....log",
  "content_hash": "sha256:...",
  "environment_fingerprint": "...",
  "revision": "..."
}
```

允许的 `kind` 包括 `command`、`file`、`diff`、`behavior_probe`、`benchmark`、`inspection`、`external_result` 和 `user_fact`。

Evidence 是不可变记录。测试重跑产生新 id，不能覆盖旧失败，从而支持实验统计和错误归因。

## 7. 专用 flow 状态

### 7.1 Repair

- `problem_statement`、`expected_behavior`
- `reproduction`、`failure_signature`
- `localization`、`hypotheses[]`、`active_hypothesis_id`
- `attempts[]`、`current_patch`、`modified_files[]`
- `last_verification_id`、`best_revision`、`status_flags`

Hypothesis 必须包含 claim、prediction、falsifying check、status 和 evidence ids。

### 7.2 Feature

- `contract`、`acceptance_items[]`、`active_item_id`
- `increments[]`、`active_increment`
- `integration_state`、`compatibility_obligations[]`
- `regression_results[]`、`completion_evidence[]`

Acceptance item 状态只能按 `pending -> active -> verified` 前进；失败返回 active，不得直接跳 verified。

### 7.3 Project

- `requirements_matrix[]`
- `architecture_decisions[]`、`module_contracts[]`
- `milestones[]`、`milestone_dag`、`active_milestone_id`
- `active_slice`、`integration_state`
- `checkpoints[]`、`best_revision`

Requirement row 包含 deliverable、oracle、owner milestone、status 和 evidence ids。

### 7.4 Optimization

- `correctness_baseline`、`performance_baseline`
- `metric_spec`、`measurement_protocol`
- `hypothesis_queue[]`、`active_hypothesis_id`
- `candidate_revision`、`candidate_results`
- `best_result`、`accepted_candidates[]`、`history[]`
- `stop_decision`、`stop_reason`

`best_result` 必须同时记录 revision、主指标分布、正确性 evidence 和环境 fingerprint。

### 7.5 Transform

- `mode` (`refactor | migration`)、`target`
- `invariants[]`、`compatibility_obligations[]`
- `behavior_baseline`、`build_baseline`、`compatibility_matrix[]`
- `steps[]`、`active_step_id`、`accepted_steps[]`
- `current_revision`、`candidate_revision`、`deferred_cleanup[]`

### 7.6 Generalist

- `outcomes[]`、`subgoals[]`、`dependency_graph`
- `active_subgoal_id`、`selected_skill`
- `execution_result`、`last_verification_id`
- `history[]`、`routing_signal`、`completion_evidence[]`

每个 subgoal 必须有局部 oracle，否则只能处于 `needs_decomposition`。

## 8. Handoff

handoff 是 Markdown，固定包含：

```markdown
# Session Handoff
## Goal And Constraints
## Current Node And Work Item
## Accepted Work
## Evidence And Commands
## Failed Attempts
## Workspace State
## Open Risks And Unknowns
## Exact Next Action
```

必填内容：state revision、active node、active flow、base/current/accepted revision、dirty files、最近 passing/failing evidence ids、未完成 work item 和下一条建议命令。

禁止写入 handoff：大段 transcript、隐藏推理、无来源猜测、完整日志、已被证伪但未标注的结论。

## 9. Memory

Memory 记录统一 envelope：

```json
{
  "memory_id": "mem-...",
  "type": "fact",
  "scope": "run",
  "statement": "...",
  "status": "confirmed",
  "confidence": 0.95,
  "source_evidence_ids": ["ev-..."],
  "created_at": "RFC3339",
  "supersedes": null,
  "expires_when": "dependency lock changes"
}
```

类型：

- `fact`：由工具或文件确认的事实；
- `decision`：架构/范围选择和理由；
- `failure`：失败 signature、已尝试方案和结果；
- `lesson_candidate`：可能可复用，但本次 run 内不得自动升级为全局 Skill。

污染控制：

- 无 evidence 的模型判断只能标为 `hypothesis`，不进入 confirmed facts。
- 新事实与旧事实冲突时建立 supersedes 链，不静默覆盖。
- 路径、revision、依赖版本变化时按 `expires_when` 失效。
- 相同 statement 以规范化 hash 去重；保留来源并合并引用。
- 全局 memory 只接受跨至少两个独立任务验证的 lesson candidate，且需要人工或离线审核。

## 10. 原子提交协议

一次节点迁移使用以下顺序：

1. 写 `attempt.status=running` 并 fsync。
2. 执行模型/工具，原始输出先写独立日志。
3. 校验 `NodeResult` schema、允许字段和合法 route。
4. 写新的 evidence/memory append-only 记录并 fsync。
5. 基于旧 `state.revision` 应用 patch，写 `state.json.tmp`。
6. fsync 临时文件和目录，原子 rename 为 `state.json`。
7. 将 attempt 标为 succeeded/failed。
8. 追加 `node_transition` event。

若恢复时 state revision 已变化，旧 attempt 不能直接提交，必须重新读取状态并判断是否仍适用。

## 11. Events 与实验指标

`events.jsonl` 至少记录：

- run created/resumed/paused/completed；
- node prepared/started/finished/transitioned；
- model call、tool call、tool result；
- context threshold、handoff written、session switched；
- verifier result、checkpoint accepted、route changed；
- retry、stagnation、limit reached、user wait；
- final completion gate 的每项结果。

可直接由事件流计算：运行时长、模型/工具调用数、会话切换次数、每 flow 循环数、重复动作率、验证失败率、提前完成次数、恢复成功率和每个 mandatory oracle 的最终状态。
