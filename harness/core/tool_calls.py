from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
SINGLE_QUOTED_KEY_RE = re.compile(r"(?P<prefix>[{,]\s*)'(?P<key>[^'\\]+)'(\s*:)")
SINGLE_QUOTED_VALUE_RE = re.compile(r":\s*'(?P<value>[^'\\]*)'")
TOOL_HINT_RE = re.compile(
    r'["\'](?:tool|name)["\']\s*:|"arguments"\s*:|"args"\s*:|```(?:json)?',
    re.IGNORECASE,
)

REPAIR_OBSERVATION = (
    "Tool call JSON was invalid or incomplete. "
    "Respond with ONLY a single valid JSON object shaped like "
    '{"tool": "tool_name", "arguments": {"key": "value"}} '
    "with double-quoted keys/strings, no trailing commas, and no extra prose."
)


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


def _close_unbalanced_braces(text: str) -> str:
    """Append missing } / ] closers when a truncated object is likely."""
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escaped = False
    for char in text:
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
            depth_brace += 1
        elif char == "}":
            depth_brace = max(0, depth_brace - 1)
        elif char == "[":
            depth_bracket += 1
        elif char == "]":
            depth_bracket = max(0, depth_bracket - 1)
    if in_string:
        text = text + '"'
    return text + ("]" * depth_bracket) + ("}" * depth_brace)


def _extract_candidate_objects(text: str) -> list[str]:
    """Collect likely JSON object strings from free-form model text."""
    candidates: list[str] = []
    for match in FENCED_JSON_RE.finditer(text):
        candidates.append(match.group(1).strip())
    for payload in _balanced_json_objects(text):
        if payload not in candidates:
            candidates.append(payload)
    if not candidates:
        start = text.find("{")
        if start >= 0:
            candidates.append(text[start:].strip())
    return candidates


def repair_json_tool_payload(text: str) -> str | None:
    """
    Fix common model JSON mistakes and return a parseable object string, or None.

    Handles: trailing commas, single-quoted keys/values, missing closers,
    and extracting the first balanced/fenced object from free-form text.
    """
    if not text or not text.strip():
        return None

    for raw in _extract_candidate_objects(text):
        repaired = _apply_json_repairs(raw)
        if repaired is not None:
            return repaired
    return _apply_json_repairs(text.strip())


def _apply_json_repairs(payload: str) -> str | None:
    """Try increasingly aggressive repairs on a single JSON-ish payload."""
    variants: list[str] = [payload]
    no_trailing = TRAILING_COMMA_RE.sub(r"\1", payload)
    if no_trailing != payload:
        variants.append(no_trailing)
    keys_fixed = SINGLE_QUOTED_KEY_RE.sub(r'\g<prefix>"\g<key>"\3', no_trailing)
    if keys_fixed not in variants:
        variants.append(keys_fixed)
    values_fixed = SINGLE_QUOTED_VALUE_RE.sub(
        lambda m: ': "' + m.group("value").replace('"', '\\"') + '"',
        keys_fixed,
    )
    if values_fixed not in variants:
        variants.append(values_fixed)

    expanded: list[str] = []
    for variant in variants:
        expanded.append(variant)
        closed = _close_unbalanced_braces(variant)
        if closed != variant:
            expanded.append(closed)

    for candidate in expanded:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return candidate
    return None


def _tool_call_from_data(data: object) -> ToolCall | None:
    if not isinstance(data, dict):
        return None
    name = data.get("tool") or data.get("name")
    arguments = data.get("arguments") or data.get("args") or {}
    if isinstance(name, str) and isinstance(arguments, dict):
        return ToolCall(name=name, arguments=arguments)
    return None


def looks_like_tool_attempt(text: str) -> bool:
    """Heuristic: text appears to be trying to emit a tool call JSON object."""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if not TOOL_HINT_RE.search(stripped):
        return False
    return "{" in stripped


def parse_tool_call(text: str) -> ToolCall | None:
    """Parse a tool call from model text. Tries strict JSON, then repairs."""
    payloads = [match.group(1) for match in FENCED_JSON_RE.finditer(text)]
    if not payloads:
        payloads = [
            payload
            for payload in _balanced_json_objects(text)
            if '"tool"' in payload or '"name"' in payload or "'tool'" in payload or "'name'" in payload
        ]

    for payload in payloads:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            repaired = repair_json_tool_payload(payload)
            if repaired is None:
                continue
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError:
                continue
        call = _tool_call_from_data(data)
        if call is not None:
            return call

    if looks_like_tool_attempt(text):
        repaired = repair_json_tool_payload(text)
        if repaired is not None:
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError:
                return None
            return _tool_call_from_data(data)
    return None


def parse_tool_call_with_retry(
    text: str,
    *,
    attempt_repair: bool = True,
) -> tuple[ToolCall | None, bool]:
    """
    Parse a tool call and report whether repair was required.

    Returns (call_or_none, used_repair). Keeps parse_tool_call as the simple API.
    """
    if not attempt_repair:
        payloads = [match.group(1) for match in FENCED_JSON_RE.finditer(text)]
        if not payloads:
            payloads = [
                payload
                for payload in _balanced_json_objects(text)
                if '"tool"' in payload or '"name"' in payload
            ]
        for payload in payloads:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            call = _tool_call_from_data(data)
            if call is not None:
                return call, False
        return None, False

    strict_call, _ = parse_tool_call_with_retry(text, attempt_repair=False)
    if strict_call is not None:
        return strict_call, False
    repaired_call = parse_tool_call(text)
    return repaired_call, repaired_call is not None


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


def repair_observation_message() -> str:
    """Tool-role observation asking the model to re-emit valid tool JSON once."""
    return json.dumps(
        {
            "tool": "__parse_error__",
            "status": "error",
            "content": REPAIR_OBSERVATION,
        },
        indent=2,
        sort_keys=True,
    )
