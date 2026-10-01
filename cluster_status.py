import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NODES_PATH = Path("/app/nodes.json")
REPORT_PATH = Path("/home/ops/reports/cluster_latest.json")


def run(command: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def status_from_percent(value: float, warning: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "normal"


def overall_status(statuses: list[str]) -> str:
    order = {"critical": 3, "warning": 2, "unknown": 1, "normal": 0}
    return max(statuses or ["unknown"], key=lambda item: order.get(item, 1))


def local_node(node: dict[str, Any]) -> dict[str, Any]:
    load_1, _, _ = os.getloadavg()
    cpu_percent = min((load_1 / (os.cpu_count() or 1)) * 100, 100)
    disk = shutil.disk_usage("/")
    disk_percent = disk.used / disk.total * 100
    memory = read_local_memory()

    statuses = [
        status_from_percent(cpu_percent, 80, 95),
        status_from_percent(memory["percent"], 85, 95),
        status_from_percent(disk_percent, 80, 90),
    ]
    return {
        "id": node["id"],
        "type": "local",
        "role": node.get("role", "local"),
        "status": overall_status(statuses),
        "metrics": {
            "cpuLoadPercent": round(cpu_percent, 1),
            "memoryUsedMb": memory["usedMb"],
            "memoryTotalMb": memory["totalMb"],
            "memoryUsagePercent": round(memory["percent"], 1),
            "diskUsedGb": round(disk.used / 1024 ** 3, 1),
            "diskTotalGb": round(disk.total / 1024 ** 3, 1),
            "diskUsagePercent": round(disk_percent, 1),
        },
        "findings": [],
    }


def read_local_memory() -> dict[str, float]:
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        meminfo[key] = int(value.strip().split()[0])
    total = meminfo.get("MemTotal", 0) / 1024
    available = meminfo.get("MemAvailable", 0) / 1024
    used = max(total - available, 0)
    return {"usedMb": round(used), "totalMb": round(total), "percent": (used / total * 100) if total else 0}


def ssh_node(node: dict[str, Any]) -> dict[str, Any]:
    remote_script = (
        "printf 'HOSTNAME='; hostname; "
        "printf 'UPTIME='; uptime; "
        "printf 'MEM='; free -m | awk '/^Mem:/ {print $2\",\"$3\",\"$7}'; "
        "printf 'DISK='; df -P / | awk 'NR==2 {print $2\",\"$3\",\"$5}'; "
        "printf 'GPU='; command -v nvidia-smi >/dev/null 2>&1 && "
        "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu "
        "--format=csv,noheader,nounits || true"
    )
    target = f"{node['user']}@{node['host']}"
    command = [
        "ssh",
        "-i",
        node["keyPath"],
        "-p",
        str(node.get("port", 22)),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=8",
        target,
        remote_script,
    ]
    result = run(command, timeout=15)
    if result.returncode != 0:
        return {
            "id": node["id"],
            "type": "ssh",
            "role": node.get("role", "remote"),
            "status": "critical",
            "metrics": {},
            "findings": [{"severity": "critical", "title": "SSH collection failed", "evidence": result.stderr.strip()}],
        }

    parsed = parse_remote_output(result.stdout)
    statuses = [
        status_from_percent(parsed["memoryUsagePercent"], 85, 95),
        status_from_percent(parsed["diskUsagePercent"], 80, 90),
    ]
    return {
        "id": node["id"],
        "type": "ssh",
        "role": node.get("role", "remote"),
        "host": node["host"],
        "status": overall_status(statuses),
        "metrics": parsed,
        "findings": [],
    }


def parse_remote_output(output: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    gpu_lines = []
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key == "GPU" and value:
                gpu_lines.append(value)
            else:
                values[key] = value
        elif line.strip() and "GPU" in values:
            gpu_lines.append(line.strip())

    mem_total, mem_used, mem_available = parse_csv_numbers(values.get("MEM", "0,0,0"))
    disk_total_kb, disk_used_kb, disk_use = parse_disk(values.get("DISK", "0,0,0%"))
    return {
        "hostname": values.get("HOSTNAME", "unknown"),
        "uptime": values.get("UPTIME", ""),
        "memoryUsedMb": mem_used,
        "memoryTotalMb": mem_total,
        "memoryAvailableMb": mem_available,
        "memoryUsagePercent": round((mem_used / mem_total * 100) if mem_total else 0, 1),
        "diskUsedGb": round(disk_used_kb / 1024 ** 2, 1),
        "diskTotalGb": round(disk_total_kb / 1024 ** 2, 1),
        "diskUsagePercent": disk_use,
        "gpus": parse_gpus(gpu_lines),
    }


def parse_csv_numbers(value: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in value.split(",")]
    nums = [int(float(part)) if part else 0 for part in parts[:3]]
    return tuple((nums + [0, 0, 0])[:3])


def parse_disk(value: str) -> tuple[int, int, float]:
    parts = [part.strip() for part in value.split(",")]
    total = int(float(parts[0])) if len(parts) > 0 and parts[0] else 0
    used = int(float(parts[1])) if len(parts) > 1 and parts[1] else 0
    percent = float(parts[2].rstrip("%")) if len(parts) > 2 and parts[2] else 0
    return total, used, percent


def parse_gpus(lines: list[str]) -> list[dict[str, Any]]:
    gpus = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append({
            "index": int(parts[0]),
            "name": parts[1],
            "memoryUsedMb": int(float(parts[2])),
            "memoryTotalMb": int(float(parts[3])),
            "utilization": int(float(parts[4])),
            "temperature": int(float(parts[5])),
        })
    return gpus


def collect() -> dict[str, Any]:
    config = json.loads(NODES_PATH.read_text())
    nodes = []
    for node in config.get("nodes", []):
        if not node.get("enabled", True):
            continue
        if node.get("type") == "local":
            nodes.append(local_node(node))
        elif node.get("type") == "ssh":
            nodes.append(ssh_node(node))

    cluster_status = overall_status([node["status"] for node in nodes])
    findings = []
    for node in nodes:
        for finding in node.get("findings", []):
            findings.append({"nodeId": node["id"], **finding})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "cluster",
        "overallStatus": cluster_status,
        "nodes": nodes,
        "findings": findings,
    }


def main() -> None:
    status = collect()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
