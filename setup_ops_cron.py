import json
import os
import time
from pathlib import Path


CRON_STORE = Path("/app/memory/cron/jobs.json")
TIMEZONE = os.getenv("OPS_TIMEZONE", "America/New_York")
FEISHU_TARGET = os.getenv("FEISHU_NOTIFY_CHAT_ID", "").strip()


def now_ms() -> int:
    return int(time.time() * 1000)


def agent_job(job_id: str, name: str, schedule: dict, message: str, deliver: bool) -> dict:
    current = now_ms()
    return {
        "id": job_id,
        "name": name,
        "enabled": True,
        "schedule": schedule,
        "payload": {
            "kind": "agent_turn",
            "message": message,
            "deliver": deliver,
            "channel": "feishu" if deliver else None,
            "to": FEISHU_TARGET if deliver else None,
            "channelMeta": {},
            "sessionKey": f"cron:{job_id}",
        },
        "state": {
            "nextRunAtMs": None,
            "lastRunAtMs": None,
            "lastStatus": None,
            "lastError": None,
            "runHistory": [],
        },
        "createdAtMs": current,
        "updatedAtMs": current,
        "deleteAfterRun": False,
    }


def main() -> None:
    store = json.loads(CRON_STORE.read_text()) if CRON_STORE.exists() else {"version": 1, "jobs": []}
    jobs = [
        job for job in store.get("jobs", [])
        if job.get("id") not in {"ops-light-inspection", "ops-daily-report", "ops-skill-dream"}
    ]

    deliver = bool(FEISHU_TARGET)
    jobs.append(agent_job(
        "ops-light-inspection",
        "Ops light inspection every 15 minutes",
        {"kind": "every", "atMs": None, "everyMs": 15 * 60 * 1000, "expr": None, "tz": None},
        (
            "执行一次本机轻量运维巡检：先通过 exec 运行 `python /app/local_status.py` "
            "刷新 reports/latest.json，然后判断 CPU、内存、磁盘、Nanobot health、近期日志风险。"
            "如果 normal，只记录结论并说明无需通知；如果 warning 或 critical，先调用 "
            "`python /app/ops_memory.py` 记录运维事件，再生成适合飞书/Slack/Telegram 发送的"
            "简短告警，包含风险等级、证据、影响和建议动作；如果 FEISHU_WEBHOOK_URL 已配置，"
            "调用 `python /app/ops_alert.py --title 'Ops Agent Alert' --message '<告警内容>'` 推送。"
        ),
        deliver,
    ))
    jobs.append(agent_job(
        "ops-daily-report",
        "Daily ops report at 09:00",
        {"kind": "cron", "atMs": None, "everyMs": None, "expr": "0 9 * * *", "tz": TIMEZONE},
        (
            "生成昨日运维日报：先调用 `python /app/ops_report.py` 生成 "
            "/home/ops/reports/daily-YYYYMMDD.md 和 daily-YYYYMMDD.json，"
            "然后读取日报摘要，总结昨日总体健康状态、异常次数、关键发现、风险趋势和今日建议。"
            "如果 FEISHU_WEBHOOK_URL 已配置，调用 "
            "`python /app/ops_alert.py --title 'Daily Ops Report' --file /home/ops/reports/daily-YYYYMMDD.md` "
            "推送日报摘要。"
        ),
        deliver,
    ))
    jobs.append(agent_job(
        "ops-skill-dream",
        "Ops skill learning from incident memory",
        {"kind": "every", "atMs": None, "everyMs": 2 * 60 * 60 * 1000, "expr": None, "tz": None},
        (
            "执行一次运维自学习：调用 `python /app/ops_skill_dream.py --min-count 2`，"
            "从 /app/memory/memory/ops_incidents.jsonl 中分析 warning / critical 高频故障模式，"
            "将候选 Skill 草稿写入 /app/memory/generated_skills。"
            "只生成 draft，不自动启用；如果生成了新候选 Skill，简短总结 pattern、事件数量和文件路径。"
        ),
        False,
    ))

    CRON_STORE.parent.mkdir(parents=True, exist_ok=True)
    CRON_STORE.write_text(json.dumps({"version": 1, "jobs": jobs}, ensure_ascii=False, indent=2))
    print(json.dumps({
        "ok": True,
        "jobs": ["ops-light-inspection", "ops-daily-report", "ops-skill-dream"],
        "deliverToFeishu": deliver,
        "target": FEISHU_TARGET or None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
