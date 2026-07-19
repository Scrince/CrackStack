from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
from typing import Any, Callable


ToolFunc = Callable[..., Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str

    @classmethod
    def success(cls, content: object) -> "ToolResult":
        if isinstance(content, str):
            return cls(ok=True, content=content)
        return cls(ok=True, content=json.dumps(content, indent=2, sort_keys=True))

    @classmethod
    def error(cls, content: object) -> "ToolResult":
        return cls(ok=False, content=str(content))


def _json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _value_matches_type(value: object, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, (int, float)) and not isinstance(value, bool))
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return True


def coerce_tool_arguments(
    arguments: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate tool arguments against a JSON-schema-like parameters object.

    Applies declared defaults, enforces required keys, and checks primitive types
    so truthy non-booleans cannot enable flags like outside_workspace.
    """
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")

    properties = parameters.get("properties") or {}
    if not isinstance(properties, dict):
        properties = {}
    required = parameters.get("required") or []
    if not isinstance(required, list):
        required = []

    result: dict[str, Any] = {}
    for key, raw in arguments.items():
        if key not in properties:
            # Unexpected keys are rejected by the signature check as well; keep strict.
            raise ValueError(f"unexpected parameter: {key}")
        result[key] = raw

    for key, schema in properties.items():
        if key in result:
            continue
        if isinstance(schema, dict) and "default" in schema:
            result[key] = schema["default"]

    missing = [key for key in required if key not in result]
    if missing:
        raise ValueError(f"missing required parameters: {missing}")

    for key, value in list(result.items()):
        schema = properties.get(key)
        if not isinstance(schema, dict):
            continue
        expected = schema.get("type")
        if expected is None:
            continue
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_value_matches_type(value, str(t)) for t in expected_types):
            raise TypeError(
                f"parameter {key!r} must be {'|'.join(str(t) for t in expected_types)}, "
                f"got {_json_type_name(value)}"
            )
    return result


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: ToolFunc

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            validated = coerce_tool_arguments(arguments or {}, self.parameters)
            accepted = set(inspect.signature(self.func).parameters)
            unexpected = set(validated) - accepted
            if unexpected:
                return ToolResult.error(f"unexpected parameters: {sorted(unexpected)}")
            # Drop keys not accepted by the callable (defaults already applied for accepted ones).
            call_args = {key: value for key, value in validated.items() if key in accepted}
            return ToolResult.success(self.func(**call_args))
        except Exception as exc:
            return ToolResult.error(f"{type(exc).__name__}: {exc}")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: ToolFunc,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
        )

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult.error(f"unknown tool: {name}")
        return tool.run(arguments)

    def specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def prompt_block(self) -> str:
        if not self._tools:
            return ""
        specs = json.dumps(self.specs(), indent=2, sort_keys=True)
        return (
            "Available tools are listed below as JSON specs. To call a tool, respond only with "
            "a fenced JSON block shaped like:\n"
            "```json\n"
            '{"tool": "tool_name", "arguments": {"key": "value"}}\n'
            "```\n"
            "After observing tool results, provide a normal final answer when done.\n"
            f"{specs}"
        )
