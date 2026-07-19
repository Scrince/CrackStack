from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from harness.backends.base import Message
from harness.paths import state_dir


def conversations_dir() -> Path:
    return state_dir() / "conversations"


def new_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    path: Path
    size: int


class ConversationStore:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or new_session_id()
        self.path = conversations_dir() / f"{self.session_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_message(self, message: Message) -> None:
        self.append_event("message", message)

    def append_event(self, event_type: str, payload: object) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def list_sessions() -> list[SessionInfo]:
    directory = conversations_dir()
    if not directory.exists():
        return []
    sessions = [
        SessionInfo(
            session_id=path.stem,
            path=path,
            size=path.stat().st_size,
        )
        for path in sorted(directory.glob("*.jsonl"), reverse=True)
    ]
    return sessions


def read_session(session_id: str) -> list[dict]:
    path = conversations_dir() / f"{session_id}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"session not found: {session_id}")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records
