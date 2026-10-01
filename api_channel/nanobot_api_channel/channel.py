import asyncio
import contextlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web
from nanobot.bus.events import OutboundMessage
from nanobot.channels.base import BaseChannel


class ApiChannel(BaseChannel):
    name = "api"
    display_name = "Local API"

    def __init__(self, config: Any, bus):
        super().__init__(config, bus)
        self.host = _get_config(config, "host", "0.0.0.0")
        self.port = int(_get_config(config, "port", 8787))
        self.timeout_s = float(_get_config(config, "timeoutS", 180))
        self.status_path = Path(str(_get_config(config, "statusPath", "/home/ops/reports/latest.json")))
        self.cluster_status_path = Path(str(_get_config(config, "clusterStatusPath", "/home/ops/reports/cluster_latest.json")))
        self.sender_id = str(_get_config(config, "senderId", "web-ui"))
        self.session_prefix = str(_get_config(config, "sessionPrefix", "web-ui"))
        self._queues: dict[str, asyncio.Queue[OutboundMessage]] = {}
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return {
            "enabled": False,
            "host": "0.0.0.0",
            "port": 8787,
            "allowFrom": ["web-ui"],
            "sendProgress": False,
            "sendToolHints": False,
            "timeoutS": 180,
            "statusPath": "/home/ops/reports/latest.json",
            "clusterStatusPath": "/home/ops/reports/cluster_latest.json",
            "senderId": "web-ui",
            "sessionPrefix": "web-ui",
        }

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_get("/api/status", self._status)
        app.router.add_post("/api/chat", self._chat)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        self._running = True

        try:
            await asyncio.Event().wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._running = False
        if self._runner:
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def send(self, msg: OutboundMessage) -> None:
        queue = self._queues.get(str(msg.chat_id))
        if queue:
            await queue.put(msg)

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "channel": self.name})

    async def _status(self, request: web.Request) -> web.Response:
        status = await asyncio.to_thread(self._read_or_generate_status)
        return web.json_response(status)

    async def _chat(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)

        content = str(payload.get("content", "")).strip()
        if not content:
            return web.json_response({"error": "content_required"}, status=400)

        conversation_id = str(payload.get("conversationId") or "default")
        request_id = str(payload.get("requestId") or uuid.uuid4())
        chat_id = f"web:{request_id}"
        session_key = f"{self.session_prefix}:{conversation_id}"
        queue: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._queues[chat_id] = queue

        try:
            await self._handle_message(
                sender_id=self.sender_id,
                chat_id=chat_id,
                content=content,
                media=[],
                metadata={"source": "dashboard", "request_id": request_id},
                session_key=session_key,
            )
            messages = await self._collect_replies(queue)
            return web.json_response(
                {
                    "requestId": request_id,
                    "conversationId": conversation_id,
                    "messages": messages,
                }
            )
        except asyncio.TimeoutError:
            return web.json_response({"error": "agent_timeout", "requestId": request_id}, status=504)
        finally:
            self._queues.pop(chat_id, None)

    async def _collect_replies(self, queue: asyncio.Queue[OutboundMessage]) -> list[dict[str, Any]]:
        first = await asyncio.wait_for(queue.get(), timeout=self.timeout_s)
        replies = [serialize_message(first)]

        while True:
            with contextlib.suppress(asyncio.TimeoutError):
                msg = await asyncio.wait_for(queue.get(), timeout=0.8)
                replies.append(serialize_message(msg))
                continue
            break

        return replies

    def _read_or_generate_status(self) -> dict[str, Any]:
        if Path("/app/nodes.json").exists():
            result = subprocess.run(
                ["python", "/app/cluster_status.py"],
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)

            if self.cluster_status_path.exists():
                return json.loads(self.cluster_status_path.read_text())

            return {
                "timestamp": None,
                "mode": "cluster",
                "overallStatus": "critical",
                "nodes": [],
                "findings": [
                    {
                        "title": "多节点状态采集失败",
                        "severity": "critical",
                        "evidence": result.stderr or result.stdout or "cluster_status.py failed",
                        "recommendation": "检查 nodes.json、SSH key 挂载和 ops-agent 容器日志",
                    }
                ],
            }

        result = subprocess.run(
            ["python", "/app/local_status.py"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)

        if self.status_path.exists():
            return json.loads(self.status_path.read_text())

        return {
            "timestamp": None,
            "overallStatus": "unknown",
            "metrics": [],
            "findings": [
                {
                    "title": "状态采集失败",
                    "severity": "warning",
                    "evidence": result.stderr or result.stdout or "local_status.py failed",
                    "recommendation": "检查 ops-agent 容器日志",
                }
            ],
        }


def serialize_message(msg: OutboundMessage) -> dict[str, Any]:
    return {
        "content": msg.content,
        "media": msg.media,
        "metadata": msg.metadata,
    }


def _get_config(config: Any, key: str, default: Any) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)
