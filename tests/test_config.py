from __future__ import annotations

from pathlib import Path

from harness.config import load_config


def test_config_resolves_relative_to_harness_root(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    (tmp_path / "models").mkdir()
    config = tmp_path / "config.toml"
    config.write_text(
        """
[model]
backend = "gguf"
path = "models/example.gguf"

[workspace]
root = "workspace"
""".strip(),
        encoding="utf-8",
    )

    loaded = load_config(config)
    assert loaded.model.resolved_path == tmp_path / "models" / "example.gguf"
    assert loaded.workspace.resolved_root == tmp_path / "workspace"


def test_model_path_must_stay_under_models(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    config = tmp_path / "config.toml"
    config.write_text('[model]\npath = "workspace/not-a-model.gguf"\n', encoding="utf-8")

    loaded = load_config(config)
    try:
        _ = loaded.model.resolved_path
    except ValueError as exc:
        assert "models/" in str(exc)
    else:
        raise AssertionError("model paths outside models/ should be rejected")
