from __future__ import annotations

from typing import Any, Iterable, Sequence

from harness.backends.base import BackendResponse, GenerateConfig, Message, ModelBackend
from harness.core.agent import Conversation
from harness.tools.registry import ToolRegistry


class NativeToolBackend(ModelBackend):
    supports_native_tools = True

    def __init__(self):
        self.received_specs: Sequence[dict[str, Any]] = []

    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        raise AssertionError("native tool backend should use generate_with_tools")

    def generate_with_tools(
        self,
        messages: Sequence[Message],
        config: GenerateConfig,
        tool_specs: Sequence[dict[str, Any]],
    ) -> BackendResponse:
        self.received_specs = tool_specs
        return BackendResponse(text="native response")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield "native response"


def test_agent_uses_native_tool_hook_when_backend_supports_it():
    backend = NativeToolBackend()
    registry = ToolRegistry()
    registry.register(
        "noop",
        "No operation.",
        {"type": "object", "properties": {}, "required": []},
        lambda: "ok",
    )
    convo = Conversation(backend=backend, generate_config=GenerateConfig(), tools=registry)

    assert convo.ask("hello") == "native response"
    assert backend.received_specs[0]["name"] == "noop"
