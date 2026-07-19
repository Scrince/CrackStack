from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .base import BackendResponse, GenerateConfig, Message, ModelBackend


class TransformersBackend(ModelBackend):
    supports_native_tools = False

    def __init__(self, model_path: Path, context_size: int = 4096):
        self.model_path = model_path
        self.context_size = context_size
        self._pipeline = None

    def load(self) -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "transformers is not available for this platform runtime. "
                "Install or vendor the matching dependencies first."
            ) from exc
        self._pipeline = pipeline("text-generation", model=str(self.model_path))

    def _prompt(self, messages: Sequence[Message]) -> str:
        return "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages) + "\nassistant:"

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        if self._pipeline is None:
            self.load()
        assert self._pipeline is not None
        result = self._pipeline(
            self._prompt(messages),
            max_new_tokens=config.max_tokens,
            temperature=config.temperature,
            do_sample=config.temperature > 0,
        )
        text = result[0]["generated_text"].split("assistant:", maxsplit=-1)[-1].strip()
        return BackendResponse(text=text, finish_reason=None)

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        yield self.generate(messages, config).text
