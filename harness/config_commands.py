from __future__ import annotations

from pathlib import Path

from harness.config import HarnessConfig, dumps_config, load_config, save_config, with_model_path
from harness.models import discover_gguf_models, display_model_path


def show_config(config: HarnessConfig | None = None) -> str:
    return dumps_config(config or load_config()).rstrip()


def select_model(model_ref: str) -> str:
    models = discover_gguf_models()
    if not models:
        raise FileNotFoundError("no .gguf models found under models/")

    selected = None
    for index, model in enumerate(models, start=1):
        display = display_model_path(model)
        if model_ref == str(index) or model_ref == display or Path(model_ref).as_posix() == display:
            selected = display
            break

    if selected is None:
        choices = ", ".join(f"{idx}:{display_model_path(path)}" for idx, path in enumerate(models, start=1))
        raise ValueError(f"unknown model {model_ref!r}; choose one of {choices}")

    config = with_model_path(load_config(), f"models/{selected}")
    save_config(config)
    return f"selected models/{selected}"
