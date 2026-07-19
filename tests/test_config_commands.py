from __future__ import annotations

from harness.config import load_config
from harness.config_commands import select_model, show_config


def test_show_config_prints_known_sections(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))

    output = show_config()

    assert "[model]" in output
    assert "[workspace]" in output
    assert "[safety]" in output


def test_select_model_writes_relative_model_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    models = tmp_path / "models"
    models.mkdir()
    (models / "alpha.gguf").write_bytes(b"stub")

    result = select_model("1")

    assert result == "selected models/alpha.gguf"
    assert load_config(tmp_path / "config.toml").model.path == "models/alpha.gguf"


def test_select_model_rejects_unknown_choice(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    models = tmp_path / "models"
    models.mkdir()
    (models / "alpha.gguf").write_bytes(b"stub")

    try:
        select_model("missing.gguf")
    except ValueError as exc:
        assert "unknown model" in str(exc)
    else:
        raise AssertionError("unknown model choice should fail")
