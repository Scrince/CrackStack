from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


Message = dict[str, str]


@dataclass(frozen=True)
class GenerateConfig:
    max_tokens: int = 512
    temperature: float = 0.7
    stop: Sequence[str] | None = None


@dataclass(frozen=True)
class BackendResponse:
    text: str
    finish_reason: str | None = None


class ModelBackend(ABC):
    supports_native_tools: bool = False

    @abstractmethod
    def load(self) -> None:
        pass
        

    @abstractmethod
    def generate(self, messages: Sequence[Message], config: GenerateConfig) -> BackendResponse:
        pass
        

    def generate_with_tools(
        self,
        messages: Sequence[Message],
        config: GenerateConfig,
        tool_specs: Sequence[dict[str, Any]],
    ) -> BackendResponse:
        
        return self.generate(messages, config)

    @abstractmethod
    def stream(self, messages: Sequence[Message], config: GenerateConfig) -> Iterable[str]:
        pass
        
