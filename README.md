# AI Operations Agent

An AI-powered operations agent for monitoring Linux and GPU infrastructure. It combines autonomous diagnostics, scheduled health checks, incident memory, alerting, an MCP tool server, and a React dashboard—with explicit safety controls around destructive actions.

This repository is a working local-machine MVP and the foundation for a planned 14-node A100/H100 cluster deployment at Brown University.

## Why I Built It

Infrastructure monitoring tools are good at showing metrics, but they often leave diagnosis and follow-up to a human operator. I built this project to explore a safer, agentic workflow:

1. Collect real system evidence.
2. Classify the machine as healthy, warning, or critical.
3. Explain the likely issue in plain language.
4. Preserve useful incident knowledge.
5. Recommend actions without silently performing destructive operations.

The goal is not to replace observability platforms. It is to add a reasoning and automation layer that connects system data, operational knowledge, and human approval.

## What It Does

- Monitors CPU, memory, swap, disks, inodes, processes, ports, logs, and container health.
- Produces structured JSON status data and Markdown daily reports.
- Runs lightweight inspections every 15 minutes through Nanobot cron.
- Sends critical alerts through supported messaging integrations.
- Stores warning and critical incidents as structured operational memory.
- Detects repeated incident patterns and generates draft diagnostic skills for human review.
- Exposes inspection, reporting, memory, and alerting capabilities as MCP tools.
- Provides a React and TypeScript dashboard with a diagnostic chat entry point.
- Supports local and SSH-based node collection through a shared node model.
- Restricts the agent to evidence-based, read-only diagnosis by default.

## System Architecture

```text
Operator / Scheduled Job
          |
          v
  Nanobot Agent Loop <--------> LLM Provider
          |
          v
  Safety and Tool Controls
          |
   +------+------+---------+----------+
   |             |         |          |
System checks  Log scan  Ops memory  MCP tools
   |             |         |          |
   +------+------+---------+----------+
          |
          v
 Structured reports and alerts
          |
          v
 React Operations Dashboard
```

The dashboard does not execute shell commands directly. Chat requests enter through a local HTTP channel, are converted into Nanobot messages, and then pass through the normal agent, tool, and safety pipeline.

## Current Implementation

The current MVP includes:

- Local Linux health collection
- Docker and Nanobot service monitoring
- Structured status and daily-report generation
- A local HTTP channel for dashboard-to-agent communication
- A React dashboard backed by real report data
- Nanobot-native scheduled inspections
- Feishu-compatible notification routing
- Explicit incident memory
- Draft skill generation from repeated incidents
- A lightweight MCP server with operational tools
- Configuration for local and remote SSH nodes

The Brown University 14-node A100/H100 environment is the target deployment scenario, not a claim that this public repository is currently connected to that production cluster.

## MCP Tools

The project exposes its operational capabilities through `ops_mcp_server.py`:

| Tool | Purpose |
| --- | --- |
| `get_cluster_status` | Collect or read local and remote node status |
| `run_light_inspection` | Run a lightweight inspection and refresh status JSON |
| `get_daily_report` | Generate or retrieve an operations report |
| `record_incident` | Save a warning or critical incident |
| `list_recent_incidents` | Retrieve recent structured incidents |
| `generate_candidate_skill` | Generate a draft diagnostic skill from repeated failures |
| `send_ops_alert` | Send an alert through a configured webhook |

## Safety Design

Operational agents need a stricter safety model than ordinary chat assistants. This project uses several layers:

- Read-only diagnostic commands are the default.
- Conclusions must be supported by command output, logs, or metrics.
- Secrets, SSH keys, tokens, and webhook URLs are excluded from reports and version control.
- Restarting services, killing processes, deleting files, or changing configuration requires human approval.
- Cross-node operations are designed for batching and rate limiting.
- Learned skills remain drafts until reviewed by a human.
- Generated diagnostic skills may contain only safe, read-only commands.

## Technology

- **Agent runtime:** Nanobot
- **Backend:** Python 3.11
- **Tool protocol:** Model Context Protocol (MCP)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Infrastructure:** Docker Compose
- **Integrations:** Feishu, DingTalk-compatible webhooks, SSH
- **Data:** JSON reports, Markdown reports, JSONL incident memory

## Repository Structure

```text
.
├── api_channel/          # HTTP channel connecting the dashboard to Nanobot
├── docs/                 # Architecture and deployment design
├── frontend/             # React operations dashboard
├── skills/               # Server, GPU, log, and general operations skills
├── cluster_status.py     # Local and remote node collection
├── local_status.py       # Lightweight local inspection
├── ops_alert.py          # Alert delivery
├── ops_mcp_server.py     # MCP tool server
├── ops_memory.py         # Structured incident persistence
├── ops_report.py         # Daily report generation
├── ops_skill_dream.py    # Draft skill generation from incident history
└── setup_ops_cron.py     # Nanobot scheduled-job setup
```

## Run Locally

### Requirements

- Docker and Docker Compose
- A supported LLM API key

### Setup

```bash
git clone https://github.com/number8868/ops-agent.git
cd ops-agent
cp .env.example .env
cp nodes.example.json nodes.json
```

Add your provider credentials to `.env`, then start the agent:

```bash
docker compose up --build -d
```

Check the services:

```bash
curl http://localhost:8787/health
curl http://localhost:8787/api/status
docker exec ops-agent curl http://127.0.0.1:18790/health
```

Run an inspection:

```bash
docker exec ops-agent python /app/cluster_status.py
docker exec -it ops-agent nanobot agent --config config.json \
  -m "Run a complete local system inspection"
```

Configure the scheduled jobs:

```bash
docker exec ops-agent python /app/setup_ops_cron.py
docker compose restart ops-agent
```

This creates:

- A lightweight inspection every 15 minutes
- A daily operations report at 09:00
- A repeated-incident skill analysis every two hours

## Roadmap

- Validate collection against the full Brown GPU cluster.
- Add GPU utilization, temperature, power, ECC, and Xid diagnostics.
- Integrate Prometheus and Grafana as optional evidence sources.
- Add WebSocket-based dashboard updates.
- Expand node-level status into a cluster health grid.
- Add training-job and GPU-memory leak diagnosis.

## What This Project Demonstrates

- Designing an agent around real tools instead of text-only responses
- Building safe automation for infrastructure workflows
- Connecting an LLM agent to MCP, scheduled tasks, memory, and messaging channels
- Separating evidence collection, reasoning, approval, and execution
- Developing a full-stack system across Python, React, Docker, and Linux operations

For a deeper technical explanation, see [the system design document](docs/system-design.md).
