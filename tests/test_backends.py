from __future__ import annotations

from harness.backends.registry import create_backend
from harness.config import ModelConfig
from harness.backends.gguf import GGUFBackend


def test_backend_requires_model_path():
    try:
        create_backend(ModelConfig(path=""))
    except ValueError as exc:
        assert "no model path" in str(exc)
    else:
        raise AssertionError("missing model path should fail clearly")


def test_backend_auto_selects_only_discovered_gguf(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    models = tmp_path / "models"
    models.mkdir()
    (models / "only.gguf").write_bytes(b"stub")

    backend = create_backend(ModelConfig(path=""))

    assert isinstance(backend, GGUFBackend)
    assert backend.model_path == models / "only.gguf"
