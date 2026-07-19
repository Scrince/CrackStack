from __future__ import annotations

from harness.core.context import ContextManager


def test_context_manager_preserves_system_and_recent_messages():
    messages = [{"role": "system", "content": "sys"}]
    for index in range(20):
        messages.append({"role": "user", "content": f"message {index} " * 20})

    fitted = ContextManager(context_window=120, reserve_tokens=20).fit(messages)

    assert fitted[0] == {"role": "system", "content": "sys"}
    assert fitted[1]["content"].startswith("message 0")
    assert "dropped" in fitted[2]["content"]
    assert fitted[-1]["content"].startswith("message 19")
    assert len(fitted) < len(messages)
