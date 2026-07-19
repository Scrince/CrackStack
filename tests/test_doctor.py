from __future__ import annotations

from harness.config import HarnessConfig, ModelConfig, SafetyConfig, WorkspaceConfig
from harness.doctor import format_checks, run_checks


def test_doctor_reports_checks(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(),
    )

    output = format_checks(run_checks(config))

    assert "harness root" in output
    assert "active python" in output
    assert "models:" in output
    assert "workspace writable" in output
