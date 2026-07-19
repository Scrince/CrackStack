from __future__ import annotations

from harness.config import HarnessConfig, ModelConfig, SafetyConfig, WorkspaceConfig
from harness.storage.audit import audit_log_path
from harness.tools.filesystem import FilesystemTools


def make_config(tmp_path) -> HarnessConfig:
    return HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(),
    )


def test_filesystem_tools_write_read_search_and_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    tools = FilesystemTools(make_config(tmp_path))

    assert tools.create_dir("notes") == "created directory notes"
    assert tools.write_file("notes/todo.txt", "alpha\nbeta\n") == "wrote notes/todo.txt"
    assert tools.read_file("notes/todo.txt") == "alpha\nbeta\n"
    assert tools.list_dir("notes") == ["todo.txt"]
    assert tools.search_files("bet")[0]["line"] == 2
    audit = audit_log_path().read_text(encoding="utf-8")
    assert "create_dir" in audit
    assert "write_file" in audit


def test_filesystem_tools_reject_workspace_escape(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    tools = FilesystemTools(make_config(tmp_path))

    try:
        tools.read_file("../config.toml")
    except ValueError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("workspace escapes should be rejected")


def test_edit_file_applies_unified_diff(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    tools = FilesystemTools(make_config(tmp_path))
    tools.write_file("sample.txt", "one\ntwo\nthree\n")

    result = tools.edit_file(
        "sample.txt",
        "--- sample.txt\n+++ sample.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n",
    )

    assert result == "patched sample.txt"
    assert tools.read_file("sample.txt") == "one\nTWO\nthree\n"


def test_filesystem_dry_run_does_not_write(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(dry_run=True),
    )
    tools = FilesystemTools(config)

    result = tools.write_file("planned.txt", "not written")

    assert result == "dry-run: would write planned.txt (11 bytes)"
    assert not (tmp_path / "workspace" / "planned.txt").exists()


def test_filesystem_read_rejects_large_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(max_file_bytes=4),
    )
    tools = FilesystemTools(config)
    tools.write_file("large.txt", "12345")

    try:
        tools.read_file("large.txt")
    except ValueError as exc:
        assert "max_file_bytes" in str(exc)
    else:
        raise AssertionError("large files should be rejected")


def test_filesystem_search_respects_match_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(max_search_matches=1),
    )
    tools = FilesystemTools(config)
    tools.write_file("notes.txt", "match one\nmatch two\n")

    assert len(tools.search_files("match")) == 1


def test_filesystem_search_outside_workspace_returns_absolute_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(allow_outside_workspace=True),
    )
    tools = FilesystemTools(config)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "notes.txt"
    target.write_text("needle\n", encoding="utf-8")

    matches = tools.search_files("needle", "../outside", outside_workspace=True)

    assert matches == [
        {
            "path": target.resolve().as_posix(),
            "line": 1,
            "text": "needle",
        }
    ]
