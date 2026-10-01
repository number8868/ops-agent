import argparse
import json
from datetime import datetime
from pathlib import Path


MEMORY_ROOT = Path("/app/memory")
HOST_MEMORY_ROOT = Path("memory")


def resolve_memory_root() -> Path:
    if MEMORY_ROOT.exists():
        return MEMORY_ROOT
    return HOST_MEMORY_ROOT


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_markdown(path: Path, section: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(existing.rstrip() + "\n\n" + section.strip() + "\n", encoding="utf-8")


def remember(args: argparse.Namespace) -> dict:
    root = resolve_memory_root()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    severity = args.severity.lower()
    record = {
        "timestamp": now,
        "severity": severity,
        "title": args.title,
        "symptom": args.symptom,
        "evidence": args.evidence,
        "root_cause": args.root_cause,
        "resolution": args.resolution,
        "tags": [tag.strip() for tag in args.tags.split(",") if tag.strip()],
    }

    append_jsonl(root / "memory" / "ops_incidents.jsonl", record)

    if severity in {"warning", "critical"}:
        section = f"""
### [{now}] {severity.upper()} - {args.title}

- Symptom: {args.symptom}
- Evidence: {args.evidence}
- Root cause: {args.root_cause or "unknown"}
- Resolution: {args.resolution or "pending"}
- Tags: {", ".join(record["tags"]) or "ops"}
"""
        append_markdown(root / "memory" / "MEMORY.md", section)

    summary = (
        f"[OPS MEMORY] {severity.upper()} {args.title}\n"
        f"Symptom: {args.symptom}\n"
        f"Evidence: {args.evidence}\n"
        f"Root cause: {args.root_cause or 'unknown'}\n"
        f"Resolution: {args.resolution or 'pending'}"
    )
    append_jsonl(root / "memory" / "history.jsonl", {
        "cursor": next_cursor(root / "memory" / "history.jsonl"),
        "timestamp": now,
        "content": summary,
    })
    return record


def next_cursor(history_path: Path) -> int:
    if not history_path.exists():
        return 1
    cursor = 0
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            cursor = max(cursor, int(json.loads(line).get("cursor", 0)))
        except Exception:
            continue
    return cursor + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist ops incidents into Nanobot memory files.")
    parser.add_argument("--severity", required=True, choices=["normal", "warning", "critical"])
    parser.add_argument("--title", required=True)
    parser.add_argument("--symptom", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--root-cause", default="")
    parser.add_argument("--resolution", default="")
    parser.add_argument("--tags", default="ops")
    args = parser.parse_args()
    print(json.dumps(remember(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
