from __future__ import annotations

import subprocess

from harness.config import HarnessConfig, ModelConfig, SafetyConfig, WorkspaceConfig
from harness.storage.history import SelfModificationHistory
from harness.tools.registry import ToolRegistry
from harness.tools.self_modify import SelfModifyTools


def git_available() -> bool:
    return subprocess.run(["git", "--version"], capture_output=True).returncode == 0


def make_config() -> HarnessConfig:
    return HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(self_modify=True, sandbox=True),
    )


def test_self_modify_installs_generated_tool(monkeypatch, tmp_path):
    if not git_available():
        return
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    registry = ToolRegistry()
    tools = SelfModifyTools(make_config(), registry)
    source = '''
def hello(name: str = "world") -> str:
    return f"hello {name}"


def register(registry):
    registry.register(
        "hello",
        "Say hello.",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "default": "world"}},
            "required": [],
        },
        hello,
    )


def smoke_test():
    assert hello("test") == "hello test"
'''.lstrip()

    result = tools.install_tool_module("hello_tool", source)

    assert "installed plugins/generated_tools/hello_tool.py" in result
    assert registry.run("hello", {"name": "Phase 3"}).content == "hello Phase 3"


def test_self_modify_rejects_failed_sandbox(monkeypatch, tmp_path):
    if not git_available():
        return
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    registry = ToolRegistry()
    tools = SelfModifyTools(make_config(), registry)

    try:
        tools.install_tool_module("broken_tool", "def nope(:\n")
    except RuntimeError as exc:
        assert "sandbox rejected" in str(exc)
    else:
        raise AssertionError("broken generated code should be rejected")

    assert not (tmp_path / "plugins" / "generated_tools" / "broken_tool.py").exists()


def test_history_can_rollback_one_snapshot(tmp_path):
    if not git_available():
        return
    history = SelfModificationHistory(tmp_path)
    target = tmp_path / "plugins" / "generated_tools" / "tracked.txt"
    target.parent.mkdir(parents=True)
    target.write_text("one\n", encoding="utf-8")
    history.snapshot("initial")
    target.write_text("two\n", encoding="utf-8")
    history.snapshot("change")

    history.rollback(1)

    assert target.read_text(encoding="utf-8") == "one\n"


def test_history_ignores_workspace_and_unrelated_harness_files(tmp_path):
    if not git_available():
        return
    history = SelfModificationHistory(tmp_path)
    generated = tmp_path / "plugins" / "generated_tools" / "tool.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("version = 1\n", encoding="utf-8")
    history.snapshot("initial")

    workspace_file = tmp_path / "workspace" / "draft.txt"
    workspace_file.parent.mkdir(parents=True)
    workspace_file.write_text("user work\n", encoding="utf-8")
    unrelated_plugin = tmp_path / "plugins" / "manual.py"
    unrelated_plugin.write_text("manual plugin\n", encoding="utf-8")
    generated.write_text("version = 2\n", encoding="utf-8")
    history.snapshot("generated change")

    workspace_file.write_text("uncommitted user edit\n", encoding="utf-8")
    unrelated_plugin.write_text("uncommitted plugin edit\n", encoding="utf-8")
    history.rollback(1)

    assert generated.read_text(encoding="utf-8") == "version = 1\n"
    assert workspace_file.read_text(encoding="utf-8") == "uncommitted user edit\n"
    assert unrelated_plugin.read_text(encoding="utf-8") == "uncommitted plugin edit\n"
