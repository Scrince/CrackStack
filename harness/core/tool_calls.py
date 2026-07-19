from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


def _balanced_json_objects(text: str) -> list[str]:
    payloads: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                payloads.append(text[start : index + 1])
                start = None
    return payloads


def parse_tool_call(text: str) -> ToolCall | None:
    payloads = [match.group(1) for match in FENCED_JSON_RE.finditer(text)]
    if not payloads:
        payloads = [payload for payload in _balanced_json_objects(text) if '"tool"' in payload or '"name"' in payload]

    for payload in payloads:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        name = data.get("tool") or data.get("name")
        arguments = data.get("arguments") or data.get("args") or {}
        if isinstance(name, str) and isinstance(arguments, dict):
            return ToolCall(name=name, arguments=arguments)
    return None


def observation_message(call: ToolCall, ok: bool, content: str) -> str:
    status = "ok" if ok else "error"
    return json.dumps(
        {
            "tool": call.name,
            "status": status,
            "content": content,
        },
        indent=2,
        sort_keys=True,
    )
