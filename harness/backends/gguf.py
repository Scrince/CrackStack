from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .base import BackendResponse, GenerateConfig, Message, ModelBackend


class GGUFBackend(ModelBackend):
    supports_native_tools = False

    def __init__(self, model_path: Path, context_size: int = 4096, gpu_layers: int = 0):
        self.model_path = model_path
        self.context_size = context_size
        self.gpu_layers = gpu_layers
        self._llm = None

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"GGUF model not found: {self.model_path}")
        try:
            from llama_cpp import Llama
            from llama_cpp import llama_cpp as llama_lib
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not available for this platform runtime. "
                "Install or vendor the matching wheel under runtime/site-packages."
            ) from exc
        supports_gpu = bool(llama_lib.llama_supports_gpu_offload())
        if self.gpu_layers != 0 and not supports_gpu:
            raise RuntimeError(
                "gpu_layers is set but this llama-cpp-python build is CPU-only. "
                "Run scripts/install-llama-vulkan.ps1 or scripts/install-llama-cuda.ps1, "
                "or set gpu_layers = 0."
            )

        try:
            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=self.context_size,
                n_gpu_layers=self.gpu_layers,
                verbose=False,
            )
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if (
                "llama_context" in lowered
                or "failed to create" in lowered
                or "out of memory" in lowered
                or "oom" in lowered
            ):
                raise RuntimeError(
                    "Failed to create llama_context — usually not enough RAM/VRAM for this "
                    f"model with context_size={self.context_size} and gpu_layers={self.gpu_layers}. "
                    "Try lowering Context (e.g. 4K or 8K), reducing GPU layers, or both, "
                    "then click Save & reload model. "
                    f"Original error: {message}"
                ) from exc
            raise

    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        if self._llm is None:
            self.load()
        assert self._llm is not None
        result = self._llm.create_chat_completion(
            messages=list(messages),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stop=config.stop,
            stream=False,
        )
        choice = result["choices"][0]
        return BackendResponse(
            text=choice["message"]["content"] or "",
            finish_reason=choice.get("finish_reason"),
        )

    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        if self._llm is None:
            self.load()
        assert self._llm is not None
        chunks = self._llm.create_chat_completion(
            messages=list(messages),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stop=config.stop,
            stream=True,
        )
        for chunk in chunks:
            delta = chunk["choices"][0].get("delta", {})
            text = delta.get("content")
            if text:
                yield text
