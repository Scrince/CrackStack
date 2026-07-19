from __future__ import annotations

from typing import Iterable, Sequence

from harness.backends.base import BackendResponse, GenerateConfig, Message, ModelBackend
from harness.core.agent import Conversation
from harness.core.context import ContextManager


class EchoBackend(ModelBackend):
    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        return BackendResponse(text=f"echo: {messages[-1]['content']}")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield "echo: "
        yield messages[-1]["content"]


class RecordingBackend(ModelBackend):
    def __init__(self):
        self.messages: list[Message] = []

    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        self.messages = list(messages)
        return BackendResponse(text="ok")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        self.messages = list(messages)
        yield "ok"


def test_conversation_runs_with_mock_backend():
    convo = Conversation(backend=EchoBackend(), generate_config=GenerateConfig())
    assert convo.ask("hello") == "echo: hello"
    assert convo.messages[-1] == {"role": "assistant", "content": "echo: hello"}


def test_conversation_stream_records_assistant_message():
    convo = Conversation(backend=EchoBackend(), generate_config=GenerateConfig())
    assert "".join(convo.stream_ask("portable")) == "echo: portable"
    assert convo.messages[-1]["content"] == "echo: portable"


def test_context_fit_does_not_permanently_drop_transcript_messages():
    backend = RecordingBackend()
    convo = Conversation(
        backend=backend,
        generate_config=GenerateConfig(),
        context_manager=ContextManager(context_window=120, reserve_tokens=20),
    )
    convo.messages.extend(
        {"role": "user", "content": f"original task detail {index} " * 20}
        for index in range(10)
    )

    assert convo.ask("latest request") == "ok"

    assert any("original task detail 0" in message["content"] for message in convo.messages)
    assert any("original task detail 0" in message["content"] for message in backend.messages)
    assert any("dropped" in message["content"] for message in backend.messages)
    assert len(backend.messages) < len(convo.messages)
