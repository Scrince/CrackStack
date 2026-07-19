from __future__ import annotations

from typing import Iterable, Sequence

from harness.backends.base import BackendResponse, GenerateConfig, Message, ModelBackend
from harness.core.agent import Conversation
from harness.core.tool_calls import parse_tool_call
from harness.tools.registry import ToolRegistry


def test_parse_fenced_json_tool_call():
    call = parse_tool_call(
        

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


def test_conversation_can_cancel_before_generation():
    convo = Conversation(
        backend=ToolCallingBackend(),
        generate_config=GenerateConfig(),
        cancel_checker=lambda: True,
    )

    assert convo.ask("calculate") == "Stopped: canceled."
