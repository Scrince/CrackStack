from __future__ import annotations

from harness.cli import _tool_registry
from harness.config import HarnessConfig, ModelConfig, SafetyConfig, WorkspaceConfig


def test_tool_registry_contains_core_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(),
    )

    names = [spec["name"] for spec in _tool_registry(config).specs()]

    assert "read_file" in names
    assert "zip_paths" in names
    assert "install_tool_module" in names


def test_tool_prompt_contains_call_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(),
    )

    prompt = _tool_registry(config).prompt_block()

    assert '"tool": "tool_name"' in prompt
    assert "read_file" in prompt
