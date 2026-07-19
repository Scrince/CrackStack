from __future__ import annotations

from typing import Iterable, Sequence

from harness.backends.base import BackendResponse, GenerateConfig, Message, ModelBackend
from harness.core.agent import Conversation
from harness.storage.sessions import ConversationStore, list_sessions, read_session


class OneShotBackend(ModelBackend):
    def load(self) -> None:
        return None

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        return BackendResponse(text="stored reply")

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield "stored reply"


def test_conversation_store_records_messages(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    store = ConversationStore(session_id="test-session")
    convo = Conversation(
        backend=OneShotBackend(),
        generate_config=GenerateConfig(),
        store=store,
    )

    assert convo.ask("remember me") == "stored reply"

    records = read_session("test-session")
    roles = [record["payload"]["role"] for record in records if record["type"] == "message"]
    assert roles == ["system", "user", "assistant"]
    assert list_sessions()[0].session_id == "test-session"
