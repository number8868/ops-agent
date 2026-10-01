import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPORT_PATH = Path("/home/ops/reports/latest.json")


def run(command: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def status_from_percent(value: float, warning: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "normal"


def load_average() -> tuple[float, str]:
    try:
        load_1, _, _ = os.getloadavg()
    except OSError:
        return 0.0, "unknown"

    cores = os.cpu_count() or 1
    percent = min((load_1 / cores) * 100, 100)
    return percent, status_from_percent(percent, 80, 95)


def memory_usage() -> tuple[float, str, str]:
    meminfo = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            meminfo[key] = int(value.strip().split()[0])
    except Exception:
        return 0.0, "unknown", "Unable to read /proc/meminfo"

    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    used = max(total - available, 0)
    percent = (used / total) * 100 if total else 0
    detail = f"{used / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} GiB"
    return percent, status_from_percent(percent, 85, 95), detail


def disk_usage(path: str = "/") -> tuple[float, str, str]:
    usage = shutil.disk_usage(path)
    percent = (usage.used / usage.total) * 100 if usage.total else 0
    detail = f"{usage.used / 1024 ** 3:.1f} / {usage.total / 1024 ** 3:.1f} GiB"
    return percent, status_from_percent(percent, 80, 90), detail


def nanobot_health() -> tuple[str, str]:
    result = run(["curl", "-s", "http://127.0.0.1:18790/health"])
    if result.returncode == 0 and '"ok"' in result.stdout:
        return "normal", "Nanobot gateway health endpoint returned ok"
    return "critical", "Nanobot gateway health endpoint is not responding"


def recent_logs() -> tuple[str, str]:
    candidates = [Path("/var/log/syslog"), Path("/var/log/system.log"), Path("/var/log/messages")]
    for path in candidates:
        if path.exists():
            result = run(["sh", "-c", f"tail -n 200 {path} | grep -Eic 'error|failed|exception|panic|timeout|oom'"])
            count = int(result.stdout.strip() or "0") if result.returncode in (0, 1) else 0
            if count >= 20:
                return "warning", f"Found {count} suspicious log lines in {path}"
            return "normal", f"Found {count} suspicious log lines in {path}"
    return "unknown", "No standard system log file found in mounted /var/log"


def build_status() -> dict:
    cpu_percent, cpu_status = load_average()
    memory_percent, memory_status, memory_detail = memory_usage()
    disk_percent, disk_status, disk_detail = disk_usage("/")
    bot_status, bot_detail = nanobot_health()
    log_status, log_detail = recent_logs()

    metrics = [
        {
            "label": "CPU",
            "value": f"{cpu_percent:.0f}%",
            "status": cpu_status,
            "detail": "Load average normalized by CPU cores",
        },
        {
            "label": "内存",
            "value": memory_detail,
            "status": memory_status,
            "detail": f"Memory usage {memory_percent:.0f}%",
        },
        {
            "label": "磁盘",
            "value": disk_detail,
            "status": disk_status,
            "detail": f"Root filesystem usage {disk_percent:.0f}%",
        },
        {
            "label": "Nanobot",
            "value": "Running" if bot_status == "normal" else "Issue",
            "status": bot_status,
            "detail": bot_detail,
        },
    ]

    findings = [
        {
            "title": "本机状态采集完成",
            "severity": "normal",
            "evidence": "Collected CPU, memory, disk, Nanobot health and recent log signals",
            "recommendation": "Use the chat panel to ask for a deeper Nanobot inspection when needed",
        },
        {
            "title": "日志快速扫描",
            "severity": log_status,
            "evidence": log_detail,
            "recommendation": "Run a full inspection if suspicious log lines increase",
        },
    ]

    status_order = {"critical": 3, "warning": 2, "unknown": 1, "normal": 0}
    overall = max([metric["status"] for metric in metrics] + [log_status], key=lambda item: status_order[item])

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overallStatus": overall,
        "metrics": metrics,
        "findings": findings,
    }


def main() -> None:
    status = build_status()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
