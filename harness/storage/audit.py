from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from harness.paths import logs_dir


def audit_log_path() -> Path:
    return logs_dir() / "audit.log"


def log_audit(action: str, target: Path, details: dict[str, Any] | None = None) -> None:
    logs_dir().mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": str(target),
        "details": details or {},
    }
    with audit_log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
