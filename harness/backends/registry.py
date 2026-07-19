from __future__ import annotations

from .base import ModelBackend
from .gguf import GGUFBackend
from .transformers_backend import TransformersBackend
from ..config import ModelConfig
from ..models import discover_gguf_models, display_model_path


def create_backend(config: ModelConfig) -> ModelBackend:
    model_path = config.resolved_path
    if model_path is None:
        discovered = discover_gguf_models()
        if len(discovered) == 1:
            model_path = discovered[0]
        elif len(discovered) > 1:
            choices = ", ".join(display_model_path(path) for path in discovered)
            raise ValueError(f"multiple models found; set model.path to one of: {choices}")
        else:
            raise ValueError("no model path configured; put a .gguf in models/ or set model.path")

    backend = config.backend.lower()
    if backend == "gguf":
        return GGUFBackend(
            model_path=model_path,
            context_size=config.context_size,
            gpu_layers=config.gpu_layers,
        )
    if backend in {"transformers", "hf", "huggingface"}:
        return TransformersBackend(model_path=model_path, context_size=config.context_size)
    raise ValueError(f"unsupported model backend: {config.backend}")
