import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


MEMORY_ROOT = Path("/app/memory")
HOST_MEMORY_ROOT = Path("memory")
INCIDENTS_RELATIVE_PATH = Path("memory/ops_incidents.jsonl")
GENERATED_SKILLS_RELATIVE_PATH = Path("generated_skills")
LEARNING_LOG_RELATIVE_PATH = Path("memory/ops_skill_learning.jsonl")

PATTERNS = {
    "disk-pressure": {
        "keywords": {"disk", "inode", "storage", "volume", "filesystem", "磁盘", "容量"},
        "title": "Disk Pressure Diagnosis",
        "domain": "磁盘容量和 inode 压力",
        "safe_commands": ["df -h", "df -ih", "du -xh --max-depth=1 <path>", "find <path> -xdev -type f -size +1G"],
        "forbidden": ["rm", "rm -rf", "truncate", "mkfs", "mount", "umount"],
    },
    "memory-pressure": {
        "keywords": {"memory", "mem", "oom", "swap", "leak", "内存", "泄露"},
        "title": "Memory Pressure Diagnosis",
        "domain": "内存、Swap、OOM 和疑似泄露",
        "safe_commands": ["free -m", "vmstat 1 5", "ps aux --sort=-%mem | head", "dmesg | grep -i oom | tail"],
        "forbidden": ["kill", "kill -9", "systemctl restart", "reboot"],
    },
    "gpu-pressure": {
        "keywords": {"gpu", "cuda", "nvidia", "xid", "ecc", "vram", "显存", "温度"},
        "title": "GPU Pressure Diagnosis",
        "domain": "GPU 显存、温度、Xid/ECC 和训练任务异常",
        "safe_commands": [
            "nvidia-smi",
            "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits",
            "nvidia-smi pmon -c 1",
            "dmesg | grep -Ei 'NVRM|Xid|ECC' | tail",
        ],
        "forbidden": ["nvidia-smi --gpu-reset", "kill", "systemctl restart", "reboot"],
    },
    "log-anomaly": {
        "keywords": {"log", "error", "failed", "fatal", "panic", "timeout", "exception", "日志", "异常"},
        "title": "Log Anomaly Diagnosis",
        "domain": "系统日志和服务异常模式",
        "safe_commands": ["tail -n 200 <log_path>", "grep -Ei 'error|failed|fatal|panic|timeout|oom' <log_path> | tail", "journalctl -p warning -n 100"],
        "forbidden": ["sed -i", "truncate", "rm", "> <log_path>"],
    },
    "ssh-connectivity": {
        "keywords": {"ssh", "network", "timeout", "connect", "unreachable", "网络", "连接"},
        "title": "SSH Connectivity Diagnosis",
        "domain": "远程节点 SSH 连接和基础网络连通性",
        "safe_commands": ["ssh -o BatchMode=yes -o ConnectTimeout=8 <node> 'hostname; uptime'", "ping -c 3 <host>", "nc -vz <host> 22"],
        "forbidden": ["iptables", "firewall-cmd", "systemctl restart sshd", "reboot"],
    },
}


def resolve_memory_root() -> Path:
    if MEMORY_ROOT.exists():
        return MEMORY_ROOT
    return HOST_MEMORY_ROOT


def load_incidents(root: Path) -> list[dict[str, Any]]:
    path = root / INCIDENTS_RELATIVE_PATH
    if not path.exists():
        return []

    incidents = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            incidents.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return incidents


def incident_text(incident: dict[str, Any]) -> str:
    fields = [
        incident.get("title", ""),
        incident.get("symptom", ""),
        incident.get("evidence", ""),
        incident.get("root_cause", ""),
        incident.get("resolution", ""),
        " ".join(incident.get("tags", [])),
    ]
    return " ".join(str(field).lower() for field in fields)


def classify_incident(incident: dict[str, Any]) -> set[str]:
    text = incident_text(incident)
    matched = set()
    for pattern_id, pattern in PATTERNS.items():
        if any(keyword.lower() in text for keyword in pattern["keywords"]):
            matched.add(pattern_id)
    return matched or {"general-ops"}


def build_patterns(incidents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for incident in incidents:
        if incident.get("severity") not in {"warning", "critical"}:
            continue
        for pattern_id in classify_incident(incident):
            grouped[pattern_id].append(incident)
    return grouped


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "general-ops"


def summarize_evidence(incidents: list[dict[str, Any]], limit: int = 3) -> list[str]:
    summaries = []
    for incident in incidents[-limit:]:
        title = incident.get("title") or "Untitled incident"
        evidence = incident.get("evidence") or incident.get("symptom") or "no evidence"
        summaries.append(f"- {title}: {evidence}")
    return summaries


def frequent_tags(incidents: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    for incident in incidents:
        counter.update(tag for tag in incident.get("tags", []) if tag)
    return [tag for tag, _ in counter.most_common(6)]


def generated_skill_markdown(pattern_id: str, incidents: list[dict[str, Any]]) -> str:
    pattern = PATTERNS.get(pattern_id, {
        "title": "General Ops Incident Diagnosis",
        "domain": "通用运维异常",
        "safe_commands": ["uptime", "free -m", "df -h", "tail -n 100 <log_path>"],
        "forbidden": ["rm", "kill", "reboot", "shutdown"],
    })
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    tags = ", ".join(frequent_tags(incidents)) or pattern_id
    examples = "\n".join(summarize_evidence(incidents))
    safe_commands = "\n".join(f"- `{command}`" for command in pattern["safe_commands"])
    forbidden = "\n".join(f"- `{command}`" for command in pattern["forbidden"])

    return f"""# {pattern["title"]} Candidate Skill

Status: draft
Generated at: {generated_at}
Source incidents: {len(incidents)}
Tags: {tags}

## When To Use

Use this candidate skill when the Agent sees repeated symptoms related to {pattern["domain"]}.
This file is generated from historical warning / critical incidents and must be reviewed before being promoted into `skills/`.

## Historical Evidence

{examples}

## Diagnostic Flow

1. Confirm the affected node, timestamp, severity, and user-visible impact.
2. Reproduce the signal with read-only commands and capture the exact evidence.
3. Compare current evidence with historical incidents listed above.
4. Identify whether this is a one-time spike, recurring pressure, or a service-impacting fault.
5. Recommend the lowest-risk next action and clearly mark any step requiring human approval.

## Safe Commands

{safe_commands}

## Commands Requiring Explicit Human Approval

{forbidden}

## Output Format

- Pattern:
- Affected node:
- Severity:
- Evidence:
- Likely cause:
- Recommended action:
- Should notify Feishu/Slack/Telegram:

## Promotion Checklist

- [ ] Reviewed by maintainer.
- [ ] Safe command list is correct for the lab environment.
- [ ] No destructive command is allowed by default.
- [ ] Output format matches the Dashboard / alerting contract.
"""


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def generate(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_memory_root()
    incidents = load_incidents(root)
    grouped = build_patterns(incidents)
    output_root = root / GENERATED_SKILLS_RELATIVE_PATH
    output_root.mkdir(parents=True, exist_ok=True)

    generated = []
    skipped = []
    for pattern_id, pattern_incidents in sorted(grouped.items()):
        if len(pattern_incidents) < args.min_count:
            skipped.append({"pattern": pattern_id, "count": len(pattern_incidents), "reason": "below_min_count"})
            continue

        skill_dir = output_root / slugify(pattern_id)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(generated_skill_markdown(pattern_id, pattern_incidents), encoding="utf-8")
        generated.append({
            "pattern": pattern_id,
            "count": len(pattern_incidents),
            "path": str(skill_path),
            "status": "draft",
        })

    index = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "incidentCount": len(incidents),
        "minCount": args.min_count,
        "generated": generated,
        "skipped": skipped,
    }
    (output_root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(root / LEARNING_LOG_RELATIVE_PATH, index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate draft ops skills from repeated incident memory.")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum warning/critical incidents required for one candidate skill.")
    args = parser.parse_args()
    print(json.dumps(generate(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
