# LightCoder 本地环境说明

仓库：

- https://github.com/Woodie-W/LightCoder
- 本轮优化基线 commit：`04f7553e3f40be0ffb484eff5ed3c605ae363628`

本地路径：

- 代码：`/data/benchmarks/LightCoder`
- DeepSeek key：`/data/.deepseek_api_key`
- 建议运行状态目录：`/data/benchmarks/LightCoder/runs`

已完成：

- 已 clone 官方仓库
- 已安装到 conda 环境 `auto-research`
- 已通过自测：43 passed
- 已生成 skills 包：`coding-agent-skills.zip`

已准备的启动脚本：

- 环境脚本：`/data/benchmarks/LightCoder/local_env.sh`
- 启动脚本：`/data/benchmarks/LightCoder/lightcoder.sh`

脚本默认行为：

- 激活 `auto-research`
- 默认模型设为 `deepseek-v4-pro`
- 默认 base URL 设为 `https://api.deepseek.com/v1`
- 若未手工传入 `LIGHTCODER_API_KEY`，则自动读取 `/data/.deepseek_api_key`

快速检查：

```bash
bash /data/benchmarks/LightCoder/lightcoder.sh --help
```

运行示例：

```bash
mkdir -p /data/benchmarks/LightCoder/runs/demo
bash /data/benchmarks/LightCoder/lightcoder.sh run \
  "Inspect the repository and report the main modules." \
  --workspace /data/benchmarks/LightCoder \
  --state-root /data/benchmarks/LightCoder/runs/demo \
  --wall-time 10m \
  --watch
```

后续用于 benchmark 时，建议：

- 提交工作区和 `state-root` 分离
- 每个任务单独一个 `state-root`
- 继续沿用官方评测容器 / 官方任务工作区；隐藏官方评测器保持不可见，
  Agent 只可在启用 `--managed-eval` 时编写 `.lightcoder-eval/` 代理评测器

## 本地长任务优化

针对首轮 SWE-Marathon 暴露出的高调用量、低缓存命中和提前结束问题，当前本地版本增加了以下改动：

- 同一 episode 使用追加式消息历史，使 DeepSeek 能复用稳定前缀缓存
- 大型 write/bash 动作在历史中只保留摘要，避免重复发送整份源码
- standard 模式的 active work item 只保留最近证据，忽略 target、node_modules 等生成目录的 revision 噪声
- 支持一次模型响应批量执行最多 8 个独立 read/bash/write 操作
- 支持精确 edit，避免小修改重写整份文件
- long-horizon 模式在 profile 后直接进入扁平执行循环，不生成 set_plan、WorkItem DAG 或 active item；任务拆解只作为模型内部建议，不形成串行门禁
- standard 模式继续使用原有 WorkItem DAG、结构化字段归一化和 begin_verification 精确验收
- long-horizon 模式要求先生成所有可评分产物，再按实际指标增益切换策略，并通过 begin_final_verification 进入最终检查
- batch 明确为顺序执行；独立长命令必须分别在后台启动并 poll
- 没有后台任务时拒绝 wait，Harbor 对合法 waiting 状态自动 resume
- Harbor 对合法 waiting 状态每 30 秒而不是每 5 秒 resume，避免后台优化期间高频空轮询
- report 自动汇总成功响应数及 prompt/cache/completion token
- API key 通过容器环境传递，不再暴露在进程命令行中

这些改动不增加模型调用次数上限，仍以 benchmark 官方 wall time 为终止条件。
