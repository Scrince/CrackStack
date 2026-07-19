from __future__ import annotations

from pathlib import Path

from .paths import models_dir


def discover_gguf_models() -> list[Path]:
    root = models_dir()
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.gguf") if path.is_file())


def display_model_path(path: Path) -> str:
    try:
        return path.relative_to(models_dir()).as_posix()
    except ValueError:
        return path.as_posix()
