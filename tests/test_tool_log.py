from __future__ import annotations

from harness.storage.tool_log import log_tool_event, tool_log_path


def test_tool_log_records_events(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))

    log_tool_event("session-1", "call", "read_file")

    text = tool_log_path().read_text(encoding="utf-8")
    assert "session-1" in text
    assert "read_file" in text
