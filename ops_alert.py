import json
import os
import argparse
import urllib.request
from pathlib import Path


def _post_json(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def send_alert(message: str, title: str = "Ops Agent Alert") -> dict:
    """Send an alert to any configured webhook channel."""
    feishu_url = os.getenv("FEISHU_WEBHOOK_URL")
    dingtalk_url = os.getenv("DINGTALK_WEBHOOK_URL")
    sent = []
    errors = []

    if feishu_url:
        try:
            _post_json(feishu_url, {"msg_type": "text", "content": {"text": f"{title}\n\n{message}"}})
            sent.append("feishu")
        except Exception as exc:
            errors.append({"channel": "feishu", "error": str(exc)})

    if dingtalk_url:
        try:
            _post_json(dingtalk_url, {"msgtype": "text", "text": {"content": f"{title}\n\n{message}"}})
            sent.append("dingtalk")
        except Exception as exc:
            errors.append({"channel": "dingtalk", "error": str(exc)})

    return {"sent": sent, "errors": errors, "configured": {"feishu": bool(feishu_url), "dingtalk": bool(dingtalk_url)}}


def read_message(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.message:
        return args.message
    return os.getenv("ALERT_MESSAGE", "Nanobot alert test")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send ops alerts to configured webhook channels.")
    parser.add_argument("--title", default=os.getenv("ALERT_TITLE", "Ops Agent Alert"))
    parser.add_argument("--message", default="")
    parser.add_argument("--file", default="")
    parsed = parser.parse_args()
    print(json.dumps(send_alert(read_message(parsed), parsed.title), ensure_ascii=False, indent=2))
