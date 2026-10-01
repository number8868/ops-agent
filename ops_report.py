import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPORT_DIR = Path("/home/ops/reports")
HOST_REPORT_DIR = Path("reports")


def report_dir() -> Path:
    return REPORT_DIR if REPORT_DIR.exists() else HOST_REPORT_DIR


def load_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest_status(root: Path) -> dict[str, Any]:
    return load_json(root / "latest.json") or {
        "timestamp": None,
        "overallStatus": "unknown",
        "metrics": [],
        "findings": [],
    }


def load_incidents() -> list[dict[str, Any]]:
    candidates = [Path("/app/memory/memory/ops_incidents.jsonl"), Path("memory/memory/ops_incidents.jsonl")]
    for path in candidates:
        if path.exists():
            incidents = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    incidents.append(json.loads(line))
                except Exception:
                    continue
            return incidents
    return []


def build_daily_report() -> tuple[dict[str, Any], str, Path, Path]:
    root = report_dir()
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_key = now.strftime("%Y%m%d")
    status = latest_status(root)
    incidents = load_incidents()
    severities = Counter(item.get("severity", "unknown") for item in incidents)

    summary = {
        "date": date_key,
        "generatedAt": now.isoformat(),
        "overallStatus": status.get("overallStatus", "unknown"),
        "latestStatusTimestamp": status.get("timestamp"),
        "metricCount": len(status.get("metrics", [])),
        "findingCount": len(status.get("findings", [])),
        "incidentCount": len(incidents),
        "severityCounts": dict(severities),
        "metrics": status.get("metrics", []),
        "findings": status.get("findings", []),
        "recentIncidents": incidents[-5:],
    }

    md = render_markdown(summary)
    json_path = root / f"daily-{date_key}.json"
    md_path = root / f"daily-{date_key}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    return summary, md, json_path, md_path


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# Daily Ops Report - {summary['date']}",
        "",
        f"- Generated at: {summary['generatedAt']}",
        f"- Overall status: {summary['overallStatus']}",
        f"- Latest status timestamp: {summary.get('latestStatusTimestamp') or 'N/A'}",
        f"- Incident count: {summary['incidentCount']}",
        "",
        "## Metrics",
        "",
    ]
    for metric in summary.get("metrics", []):
        lines.append(f"- {metric.get('label')}: {metric.get('value')} ({metric.get('status')}) - {metric.get('detail')}")

    lines.extend(["", "## Findings", ""])
    for finding in summary.get("findings", []):
        lines.append(f"- [{finding.get('severity')}] {finding.get('title')}: {finding.get('evidence')} -> {finding.get('recommendation')}")

    lines.extend(["", "## Recent Incidents", ""])
    if not summary.get("recentIncidents"):
        lines.append("- No recorded warning/critical incidents.")
    else:
        for incident in summary["recentIncidents"]:
            lines.append(f"- [{incident.get('severity')}] {incident.get('title')} ({incident.get('timestamp')}): {incident.get('symptom')}")

    lines.extend(["", "## Suggestions", ""])
    if summary["overallStatus"] == "normal":
        lines.append("- System is healthy. Continue routine inspection.")
    elif summary["overallStatus"] == "warning":
        lines.append("- Review warning findings and consider a deeper agent inspection.")
    else:
        lines.append("- Critical status detected. Notify the responsible operator and inspect immediately.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily ops report files.")
    parser.add_argument("--print-markdown", action="store_true")
    args = parser.parse_args()
    summary, md, json_path, md_path = build_daily_report()
    output = {"summary": summary, "jsonPath": str(json_path), "markdownPath": str(md_path)}
    print(md if args.print_markdown else json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
