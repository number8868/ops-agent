import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool


ops_server = Server("brown-lab-ops-mcp")

REPORT_ROOT = Path("/home/ops/reports")
MEMORY_ROOT = Path("/app/memory")
APP_ROOT = Path("/app")


def run_python(script: str, args: list[str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(APP_ROOT / script), *(args or [])],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def json_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def command_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    parsed: Any = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = stdout

    return {
        "ok": result.returncode == 0,
        "returnCode": result.returncode,
        "data": parsed,
        "stderr": stderr,
    }


@ops_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_cluster_status",
            description="Collect current local and SSH remote node status, including CPU, memory, disk, uptime, and GPU detection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "refresh": {
                        "type": "boolean",
                        "description": "When true, run cluster_status.py before returning the report.",
                        "default": True,
                    }
                },
            },
        ),
        Tool(
            name="run_light_inspection",
            description="Run local lightweight inspection and refresh reports/latest.json.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_daily_report",
            description="Read an existing daily ops report or generate today's report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Report date in YYYYMMDD. Leave empty for today's generated report.",
                    },
                    "generate": {
                        "type": "boolean",
                        "description": "When true, run ops_report.py before reading the report.",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="record_incident",
            description="Persist a warning or critical ops incident into the project memory store.",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["normal", "warning", "critical"]},
                    "title": {"type": "string"},
                    "symptom": {"type": "string"},
                    "evidence": {"type": "string"},
                    "rootCause": {"type": "string"},
                    "resolution": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["severity", "title"],
            },
        ),
        Tool(
            name="list_recent_incidents",
            description="Return recent structured ops incidents from memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    "severity": {"type": "string", "enum": ["normal", "warning", "critical"]},
                },
            },
        ),
        Tool(
            name="generate_candidate_skill",
            description="Analyze incident memory and generate draft candidate skills under memory/generated_skills.",
            inputSchema={
                "type": "object",
                "properties": {
                    "minCount": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 2,
                    }
                },
            },
        ),
        Tool(
            name="send_ops_alert",
            description="Send an ops alert through configured webhook channels such as Feishu or DingTalk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "file": {"type": "string", "description": "Optional file path to send as alert content."},
                },
                "required": ["title"],
            },
        ),
    ]


@ops_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "get_cluster_status":
            return get_cluster_status(arguments)
        if name == "run_light_inspection":
            return run_light_inspection()
        if name == "get_daily_report":
            return get_daily_report(arguments)
        if name == "record_incident":
            return record_incident(arguments)
        if name == "list_recent_incidents":
            return list_recent_incidents(arguments)
        if name == "generate_candidate_skill":
            return generate_candidate_skill(arguments)
        if name == "send_ops_alert":
            return send_ops_alert(arguments)
        return json_text({"ok": False, "error": f"unknown tool: {name}"})
    except Exception as exc:
        return json_text({"ok": False, "error": str(exc)})


def get_cluster_status(arguments: dict[str, Any]) -> list[TextContent]:
    refresh = arguments.get("refresh", True)
    if refresh:
        result = run_python("cluster_status.py", timeout=30)
        return json_text(command_result(result))

    path = REPORT_ROOT / "cluster_latest.json"
    if not path.exists():
        return json_text({"ok": False, "error": "cluster_latest.json not found"})
    return json_text({"ok": True, "data": json.loads(path.read_text(encoding="utf-8"))})


def run_light_inspection() -> list[TextContent]:
    result = run_python("local_status.py", timeout=20)
    return json_text(command_result(result))


def get_daily_report(arguments: dict[str, Any]) -> list[TextContent]:
    generate = arguments.get("generate", True)
    if generate:
        result = run_python("ops_report.py", timeout=30)
        if result.returncode != 0:
            return json_text(command_result(result))

    requested_date = str(arguments.get("date") or "").strip()
    if requested_date:
        path = REPORT_ROOT / f"daily-{requested_date}.md"
    else:
        reports = sorted(REPORT_ROOT.glob("daily-*.md"), reverse=True)
        path = reports[0] if reports else None

    if not path or not path.exists():
        return json_text({"ok": False, "error": "daily report not found"})

    return json_text({
        "ok": True,
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
    })


def record_incident(arguments: dict[str, Any]) -> list[TextContent]:
    tags = arguments.get("tags", [])
    args = [
        "--severity", str(arguments.get("severity", "warning")),
        "--title", str(arguments.get("title", "Untitled incident")),
        "--symptom", str(arguments.get("symptom", "")),
        "--evidence", str(arguments.get("evidence", "")),
        "--root-cause", str(arguments.get("rootCause", "")),
        "--resolution", str(arguments.get("resolution", "")),
        "--tags", ",".join(str(tag) for tag in tags) if isinstance(tags, list) else str(tags),
    ]
    result = run_python("ops_memory.py", args, timeout=20)
    return json_text(command_result(result))


def list_recent_incidents(arguments: dict[str, Any]) -> list[TextContent]:
    limit = int(arguments.get("limit", 10))
    severity = arguments.get("severity")
    path = MEMORY_ROOT / "memory" / "ops_incidents.jsonl"
    if not path.exists():
        return json_text({"ok": True, "incidents": []})

    incidents = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            incident = json.loads(line)
        except json.JSONDecodeError:
            continue
        if severity and incident.get("severity") != severity:
            continue
        incidents.append(incident)

    return json_text({"ok": True, "incidents": incidents[-limit:]})


def generate_candidate_skill(arguments: dict[str, Any]) -> list[TextContent]:
    min_count = int(arguments.get("minCount", 2))
    result = run_python("ops_skill_dream.py", ["--min-count", str(min_count)], timeout=30)
    return json_text(command_result(result))


def send_ops_alert(arguments: dict[str, Any]) -> list[TextContent]:
    args = ["--title", str(arguments.get("title", "Ops Agent Alert"))]
    message = str(arguments.get("message", "")).strip()
    file_path = str(arguments.get("file", "")).strip()

    if message:
        args.extend(["--message", message])
    if file_path:
        args.extend(["--file", file_path])
    if not message and not file_path:
        args.extend(["--message", "Ops alert triggered without additional details."])

    result = run_python("ops_alert.py", args, timeout=20)
    return json_text(command_result(result))


@ops_server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="ops://reports/cluster_latest",
            name="Latest Cluster Status",
            description="Latest generated local and remote node status report.",
            mimeType="application/json",
        ),
        Resource(
            uri="ops://memory/incidents",
            name="Ops Incident Memory",
            description="Structured warning and critical incident memory.",
            mimeType="application/jsonl",
        ),
        Resource(
            uri="ops://skills/generated",
            name="Generated Candidate Skills",
            description="Draft skills generated from repeated incident patterns.",
            mimeType="application/json",
        ),
    ]


@ops_server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "ops://reports/cluster_latest":
        return (REPORT_ROOT / "cluster_latest.json").read_text(encoding="utf-8")
    if uri == "ops://memory/incidents":
        return (MEMORY_ROOT / "memory" / "ops_incidents.jsonl").read_text(encoding="utf-8")
    if uri == "ops://skills/generated":
        index = MEMORY_ROOT / "generated_skills" / "index.json"
        return index.read_text(encoding="utf-8") if index.exists() else "{}"
    raise ValueError(f"unsupported resource URI: {uri}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await ops_server.run(read_stream, write_stream, ops_server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
