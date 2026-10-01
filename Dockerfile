FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    sysstat \
    net-tools \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir nanobot-ai mcp

WORKDIR /app

RUN mkdir -p /home/ops/reports /app/memory /app/workspace

COPY api_channel/ ./api_channel/
RUN pip install --no-cache-dir -e ./api_channel

COPY AGENTS.md config.json ./
COPY skills/ ./skills/
COPY ops_alert.py local_status.py setup_ops_cron.py ops_memory.py ops_report.py cluster_status.py ops_skill_dream.py ops_mcp_server.py ./

ENV DEEPSEEK_API_KEY="" \
    FEISHU_APP_ID="" \
    FEISHU_APP_SECRET="" \
    FEISHU_ENCRYPT_KEY="" \
    FEISHU_VERIFICATION_TOKEN="" \
    FEISHU_NOTIFY_CHAT_ID="" \
    FEISHU_WEBHOOK_URL="" \
    DINGTALK_WEBHOOK_URL=""

EXPOSE 18790

CMD ["nanobot", "gateway", "--config", "config.json"]
