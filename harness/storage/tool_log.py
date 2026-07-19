from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from harness.paths import logs_dir


def tool_log_path() -> Path:
    return logs_dir() / "tool_calls.log"


def log_tool_event(session_id: str, kind: str, message: str) -> None:
    logs_dir().mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "kind": kind,
        "message": message,
    }
    with tool_log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
