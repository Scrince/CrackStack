from __future__ import annotations

from typing import Iterable, Sequence

from harness.backends.base import BackendResponse, GenerateConfig, Message, ModelBackend
from harness.core.agent import Conversation
from harness.core.tool_calls import (
    looks_like_tool_attempt,
    parse_tool_call,
    parse_tool_call_with_retry,
    repair_json_tool_payload,
)
from harness.tools.registry import ToolRegistry


def test_parse_fenced_json_tool_call():
    call = parse_tool_call(
        '```json\n{"tool": "read_file", "arguments": {"path": "notes.txt"}}\n```'
    )
    assert call is not None
    assert call.name == "read_file"
    assert call.arguments == {"path": "notes.txt"}


def test_parse_bare_json_tool_call():
    call = parse_tool_call('{"tool": "list_dir", "arguments": {"path": "."}}')
    assert call is not None
    assert call.name == "list_dir"


def test_parse_bare_nested_json_tool_call():
    call = parse_tool_call(
        'thinking first {"tool": "write_file", "arguments": {"path": "a.json", "content": "{\\"x\\": 1}"}} done'
    )
    assert call is not None
    assert call.name == "write_file"
    assert call.arguments["content"] == '{"x": 1}'


def test_repair_trailing_comma():
    raw = '{"tool": "list_dir", "arguments": {"path": ".",},}'
    repaired = repair_json_tool_payload(raw)
    assert repaired is not None
    call = parse_tool_call(raw)
    assert call is not None
    assert call.name == "list_dir"
    assert call.arguments == {"path": "."}


def test_repair_single_quoted_keys_and_values():
    raw = "{'tool': 'read_file', 'arguments': {'path': 'notes.txt'}}"
    call = parse_tool_call(raw)
    assert call is not None
    assert call.name == "read_file"
    assert call.arguments == {"path": "notes.txt"}


def test_repair_missing_closing_braces():
    raw = '{"tool": "list_dir", "arguments": {"path": "."'
    repaired = repair_json_tool_payload(raw)
    assert repaired is not None
    call = parse_tool_call(raw)
    assert call is not None
    assert call.name == "list_dir"
    assert call.arguments["path"] == "."


def test_repair_extracts_first_balanced_object():
    text = 'Sure, I will call a tool now: {"tool": "list_dir", "arguments": {"path": "src"}}, hope that works.'
    call = parse_tool_call(text)
    assert call is not None
    assert call.name == "list_dir"


def test_repair_fenced_with_trailing_comma():
    text = '```json\n{"tool": "read_file", "arguments": {"path": "a.py",},}\n```'
    call = parse_tool_call(text)
    assert call is not None
    assert call.name == "read_file"
    assert call.arguments == {"path": "a.py"}


def test_looks_like_tool_attempt():
    assert looks_like_tool_attempt('{"tool": "x", "arguments": {')
    assert looks_like_tool_attempt("```json\n{broken")
    assert not looks_like_tool_attempt("Here is a normal answer with no tools.")


def test_parse_tool_call_with_retry_reports_repair():
    strict, used = parse_tool_call_with_retry(
        '{"tool": "list_dir", "arguments": {"path": ".",}}',
        attempt_repair=True,
    )
    assert strict is not None
    assert used is True
    ok, used_strict = parse_tool_call_with_retry(
        '{"tool": "list_dir", "arguments": {"path": "."}}',
        attempt_repair=True,
    )
    assert ok is not None
    assert used_strict is False


class ToolCallingBackend(ModelBackend):
    def __init__(self):
        self.calls = 0

    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        self.calls += 1
        if self.calls == 1:
            return BackendResponse(
                text='```json\n{"tool": "double", "arguments": {"value": 21}}\n```'
            )
        assert messages[-1]["role"] == "tool"
        return BackendResponse(text="The answer is 42.")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield self.generate(messages, config).text


class BrokenThenFixedToolBackend(ModelBackend):
    def __init__(self):
        self.calls = 0

    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        self.calls += 1
        if self.calls == 1:
            return BackendResponse(text='{"tool": "double", "arguments": {broken')
        if self.calls == 2:
            assert messages[-1]["role"] == "tool"
            assert "valid JSON" in messages[-1]["content"] or "parse" in messages[-1]["content"].lower()
            return BackendResponse(
                text='{"tool": "double", "arguments": {"value": 3}}'
            )
        return BackendResponse(text="doubled")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield self.generate(messages, config).text


def test_conversation_executes_tool_and_continues():
    registry = ToolRegistry()
    events = []
    registry.register(
        "double",
        "Double a number.",
        {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
        lambda value: value * 2,
    )
    convo = Conversation(
        backend=ToolCallingBackend(),
        generate_config=GenerateConfig(),
        tools=registry,
        tool_observer=lambda kind, message: events.append((kind, message)),
    )

    assert convo.ask("calculate") == "The answer is 42."
    assert any(message["role"] == "tool" for message in convo.messages)
    assert events[0][0] == "call"
    assert events[1][0] == "result"


def test_conversation_offers_parse_repair_once():
    registry = ToolRegistry()
    events = []
    registry.register(
        "double",
        "Double a number.",
        {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
        lambda value: value * 2,
    )
    backend = BrokenThenFixedToolBackend()
    convo = Conversation(
        backend=backend,
        generate_config=GenerateConfig(),
        tools=registry,
        tool_observer=lambda kind, message: events.append((kind, message)),
    )

    assert convo.ask("calculate") == "doubled"
    assert backend.calls == 3
    assert any(kind == "parse_error" for kind, _ in events)
    assert any(kind == "call" for kind, _ in events)


def test_conversation_can_cancel_before_generation():
    convo = Conversation(
        backend=ToolCallingBackend(),
        generate_config=GenerateConfig(),
        cancel_checker=lambda: True,
    )

    assert convo.ask("calculate") == "Stopped: canceled."
