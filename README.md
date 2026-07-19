# LightCoder

LightCoder 是一个 training-free、单 LLM、可持久恢复的 Long-Running 编码智能体。它面向可能持续数小时、跨越多个上下文窗口的完整工程任务，不使用现成 Agent 框架，也不引入额外的 LLM supervisor。

## Architecture

```text
CLI / benchmark adapter
        |
deterministic RunController
        |- persistent state and evidence
        |- work-item DAG and completion guards
        |- deadlines and best checkpoints
        |- context episodes and validated handoffs
        `- command supervision
        |
single CodingAgent -> OpenAI-compatible model
        |
      bash / read / write -> target workspace
```

任务按照两个正交维度路由：执行机制为 `standard | long_horizon`，工程方法为 `repair | feature | project | transformation | optimization | generalist`。路由只依据可观测任务属性，不读取 benchmark 或任务名称。

## Capabilities

- `state.json` 原子提交、revision 冲突检测和单 run lease
- dependency-aware work-item DAG，无固定 attempt/replan 上限
- 当前 workspace revision 绑定的不可变 evidence
- mandatory work item 的精确验证命令门和独立 final verification
- 仅剩约 8k token、milestone 和 provider exhaustion 触发的无限次 episode 轮换
- disk-grounded handoff、完整 transcript 归档和有界上下文重建
- 可选前台超时、后台命令、PID 身份校验、可分页日志保留与取消
- long-horizon 检查点、best artifact 和任务硬截止恢复
- 14 个按需加载、与 benchmark 无关的英文 skills
- `report` 生成实验所需的运行、验证和上下文指标

## Install

```bash
conda activate auto-research
python -m pip install --no-build-isolation -e '.[dev]'
```

配置任意 OpenAI-compatible chat-completions endpoint：

```bash
export LIGHTCODER_BASE_URL="https://api.deepseek.com/v1"
export LIGHTCODER_MODEL="deepseek-v4-pro"
export LIGHTCODER_API_KEY="$DEEPSEEK_API_KEY"
```

## Run

建议把运行状态放在提交工作区之外：

```bash
lightcoder run \
  "Implement and verify the requested system" \
  --workspace /path/to/project \
  --state-root /path/to/runtime-state \
  --wall-time 4h \
  --watch
```

`--watch` 把结构化事件输出到 stderr；最终 canonical state 输出到 stdout。`run_id` 会在启动时立即打印。

```bash
lightcoder resume RUN_ID --state-root /path/to/runtime-state --watch
lightcoder step RUN_ID --state-root /path/to/runtime-state
lightcoder status RUN_ID --state-root /path/to/runtime-state
lightcoder report RUN_ID --state-root /path/to/runtime-state
lightcoder cancel RUN_ID --state-root /path/to/runtime-state
lightcoder list --state-root /path/to/runtime-state
```

`--max-cycles N` 只让当前 CLI 调用主动 yield，不终止持久 run，也不构成 attempt 上限。

## Skills

源码 skills 位于 [`skills/`](skills/)，manifest 仅包含 14 个语义技能。构建可复现压缩包：

```bash
python tools/build_coding_agent_skills.py --build-zip
```

输出为 `coding-agent-skills.zip`。Agent 可见的 skill 内容仅使用英文；状态机、评测和设计说明保留在 [`docs/`](docs/README.md)。

## Verify

```bash
conda run -n auto-research pytest -q
python tools/build_coding_agent_skills.py --build-zip
```

`bash` 能执行目标仓库的任意命令，因此应在 benchmark 容器或其他隔离环境中运行。路径策略保护 `read`、`write`、cwd 和 runtime metadata，但不能替代操作系统级 shell sandbox。
