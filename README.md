# 本机智能运维 Agent

这是“项目一：智能运维 Agent”的 MVP 实现。当前版本先监控本机状态，完成 Nanobot 运维 Agent、巡检报告、前端看板和诊断对话入口；Brown University 实验室 14 台 A100/H100 GPU 服务器是项目背景和后续扩展目标。

## 项目目标

- 当前阶段：监控本机 CPU、内存、磁盘、日志、Docker/Nanobot 状态。
- 提供 React 运维看板，展示本机健康状态、最近巡检摘要和诊断对话入口。
- 用安全白名单约束 Agent 可执行命令，降低误操作风险。
- 预留多节点数据结构，后续可扩展到 Brown 14 台 GPU 服务器。
- 后续支持 GPU 指标、训练任务诊断、告警推送和 WebSocket 实时刷新。

## 当前状态

- 后端容器：`ops-agent`
- Nanobot gateway：容器内 `18790` 端口
- 模型 provider：`deepseek`
- 默认模型：`deepseek-v4-flash`
- 日志挂载：宿主机 `/var/log` 只读挂载到容器 `/var/log`
- 报告目录：宿主机 `./reports` 挂载到容器 `/home/ops/reports`
- 记忆目录：宿主机 `./memory` 挂载到容器 `/app/memory`
- 前端目录：`frontend/`，当前展示本机 MVP 看板，预留多节点扩展区域

## 目录说明

- `Dockerfile`：构建 Nanobot 运维 Agent 镜像。
- `docker-compose.yml`：启动 `ops-agent` 服务。
- `config.json`：Nanobot provider、模型、工具和 gateway 配置。
- `AGENTS.md`：Brown GPU 集群运维 Agent 的角色、安全边界、巡检流程和告警规则。
- `docs/system-design.md`：本机 MVP 和 Brown GPU 集群扩展设计文档。
- `nodes.example.json`：未来多节点配置示例。
- `nodes.json`：当前本机和云服务器节点配置。
- `api_channel/`：本地 HTTP channel 插件，把前端消息封装为 Nanobot `InboundMessage`。
- `setup_ops_cron.py`：写入 Nanobot 原生 cron jobs，包含 15 分钟巡检和每日 09:00 日报。
- `ops_memory.py`：将 warning / critical 运维事件写入 Nanobot memory 和结构化事件库。
- `ops_skill_dream.py`：从历史运维事件中分析高频故障模式，生成候选 Skill 草稿。
- `ops_report.py`：生成每日运维日报 Markdown/JSON。
- `cluster_status.py`：采集本机和远程 SSH 节点状态，生成集群状态 JSON。
- `ops_mcp_server.py`：轻量 MCP Server，将巡检、日报、记忆、告警和候选 Skill 生成功能封装为标准化工具。
- `mcp_config.example.json`：MCP 客户端连接 `ops-agent` 容器内工具服务的示例配置。
- `skills/ops.md`：运维巡检通用技能。
- `skills/server-monitor/SKILL.md`：服务器资源监控技能。
- `skills/gpu-monitor/SKILL.md`：GPU 资源监控技能。
- `skills/log-analyzer/SKILL.md`：日志异常诊断技能。
- `frontend/`：WebUI Dashboard 前端骨架。
- `ops_alert.py`：飞书/钉钉 webhook 告警脚本。
- `.env.example`：环境变量示例，真实密钥写入 `.env`。

## 快速启动

创建 `.env` 并填入真实密钥：

```bash
cp .env.example .env
```

`.env` 示例：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
FEISHU_APP_ID=你的飞书应用 App ID
FEISHU_APP_SECRET=你的飞书应用 App Secret
FEISHU_NOTIFY_CHAT_ID=日报和告警要投递的飞书 chat_id
```

构建并启动：

```bash
docker compose up --build -d
```

查看日志：

```bash
docker compose logs -f ops-agent
```

验证容器内部健康状态：

```bash
docker exec ops-agent curl -s http://127.0.0.1:18790/health
```

验证前端 API channel：

```bash
curl -s http://localhost:8787/health
```

读取真实看板状态：

```bash
curl -s http://localhost:8787/api/status
```

采集本机 + 云服务器状态：

```bash
docker exec ops-agent python /app/cluster_status.py
```

配置 Nanobot 原生定时任务：

```bash
docker exec ops-agent python /app/setup_ops_cron.py
docker compose restart ops-agent
```

这会创建两个 cron jobs：

- `ops-light-inspection`：每 15 分钟执行一次轻量巡检。
- `ops-daily-report`：每天 09:00 生成运维日报。
- `ops-skill-dream`：每 2 小时分析历史异常，生成候选运维 Skill 草稿。

如果 `.env` 配置了 `FEISHU_NOTIFY_CHAT_ID`，cron job 会通过 Nanobot `feishu` channel 投递消息；否则只在 Agent 内部执行并记录。

## 飞书 Channel

Nanobot 已内置 `feishu` channel。本项目在 `config.json` 中保留了配置，但默认 `enabled=false`。启用时需要：

1. 在飞书开放平台创建应用并启用机器人能力。
2. 填写 `.env` 中的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。
3. 在 `config.json` 将 `channels.feishu.enabled` 改为 `true`。
4. 重启容器。

飞书消息会走 Nanobot 原生链路：

```text
Feishu Channel -> InboundMessage -> Agent loop -> skills/tools/memory -> OutboundMessage -> Feishu
```

手动触发完整巡检：

```bash
docker exec -it ops-agent nanobot agent --config config.json -m "执行一次本机完整巡检"
```

手动生成日报：

```bash
docker exec ops-agent python /app/ops_report.py
```

测试 webhook 通知：

```bash
docker exec ops-agent python /app/ops_alert.py --title "Ops Agent Test" --message "Webhook test from ops-agent"
```

## Ops MCP Server

项目提供了一个轻量 MCP Server，用于把已有运维能力抽象为标准化 tools：

```bash
docker exec -i ops-agent python /app/ops_mcp_server.py
```

可用工具：

- `get_cluster_status`：采集或读取本机 + SSH 远程节点状态。
- `run_light_inspection`：执行本机轻量巡检，刷新 `reports/latest.json`。
- `get_daily_report`：生成或读取每日运维报告。
- `record_incident`：将 warning / critical 事件写入运维记忆。
- `list_recent_incidents`：读取最近的结构化运维事件。
- `generate_candidate_skill`：从历史异常中生成 draft 候选 Skill。
- `send_ops_alert`：通过已配置 webhook 发送运维告警。

MCP 客户端配置可参考：

```bash
mcp_config.example.json
```

这层 MCP 目前封装的是项目内真实能力，后续可以继续替换或扩展到 Prometheus、Elasticsearch、Kubernetes 等外部系统。

停止服务：

```bash
docker compose down
```

## 当前巡检范围

- 本机 CPU、负载、运行时间。
- 本机内存、Swap、磁盘、inode。
- Docker/Nanobot 容器状态。
- `/var/log` 下近期错误、异常、失败日志。
- Nanobot memory、heartbeat、cron、reports 状态。
- 巡检结果 JSON 化，为前端 Dashboard 提供数据契约。

## 记忆机制说明

Nanobot 的 MemoryConsolidator 主要负责在会话过长时压缩历史消息，并不会自动把每次巡检都写成运维知识。项目中新增了显式的运维记忆机制：

- normal 巡检只更新报告。
- warning / critical 事件写入 `memory/memory/ops_incidents.jsonl`。
- 重要事件同步写入 `memory/memory/MEMORY.md` 和 `history.jsonl`，供后续 dream/consolidation 整理。
- Agent 在发现异常或用户要求“记住这次故障”时，应调用 `ops_memory.py` 沉淀故障模式和解决方案。

## 自学习 Skill 机制

项目在 Nanobot 原生 dream 之外增加了运维领域的自学习脚本：

```bash
docker exec ops-agent python /app/ops_skill_dream.py --min-count 2
```

执行流程：

1. 读取 `memory/memory/ops_incidents.jsonl` 中的 warning / critical 事件。
2. 按磁盘、内存、GPU、日志、SSH 连接等故障模式进行归类。
3. 当某类事件达到阈值时，在 `memory/generated_skills/` 生成 draft 状态的候选 Skill。
4. 候选 Skill 包含适用场景、历史证据、安全命令、禁止操作和输出格式。
5. 候选 Skill 默认不自动启用，需要人工审核后再迁移到正式 `skills/` 目录。

这种设计让 Agent 能沉淀经验，同时避免自动生成的技能直接获得执行权限。

## 可扩展目标

- 支持 `nodes.json` 配置多个节点。
- 通过 SSH 或 sidecar agent 采集远程节点指标。
- 增加 GPU 显存、利用率、温度、功率、ECC/Xid 错误诊断。
- 将单机卡片扩展成 N 节点健康网格。
- 对 Brown 14 台 A100/H100 服务器生成集群级日报和告警。

## 前端展示

前端目标是一个 React 18 + TypeScript + Tailwind CSS 运维看板：

- 本机健康总览：CPU、内存、磁盘、Nanobot 状态。
- 巡检报告摘要：通过 `/api/status` 读取 `reports/latest.json` 的真实状态。
- 诊断对话入口：用户可输入“现在机器负载高吗？”、“帮我巡检一次”。
- 扩展节点区域：展示未来多节点/GPU 集群接入状态。
- 后续接入 WebSocket 或 `reports/latest.json` 实现真实数据刷新。

当前诊断对话已设计为调用本地 API channel：前端 `POST /api/chat`，API channel 调用 Nanobot `_handle_message(...)` 生成 `InboundMessage`，再由 Agent loop 处理 skill、tool 和 memory。

## 下一步开发

- 将 Nanobot 完整巡检输出进一步结构化，覆盖更多本机日志和 Docker 状态。
- 根据真实飞书应用信息启用 `channels.feishu.enabled`。
- 增加 `nodes.json` 多节点配置和采集抽象。
- 再扩展 GPU/Brown 集群场景。
