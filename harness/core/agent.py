from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from harness.backends.base import GenerateConfig, Message, ModelBackend
from harness.core.context import ContextManager
from harness.core.tool_calls import observation_message, parse_tool_call
from harness.storage.sessions import ConversationStore
from harness.tools.registry import ToolRegistry


DEFAULT_SYSTEM_PROMPT = (
    "You are CrackStack Codex, a local coding agent. "
    "You run fully offline against a local model and a local workspace. "
    "Prefer using tools to inspect and edit files rather than guessing. "
    "When the user attaches files, treat their contents as authoritative context. "
    "Keep paths relative to the workspace unless the user provides absolute paths. "
    "Be concise, execute the task, and explain only what is needed."
)


@dataclass
class Conversation:
    backend: ModelBackend
    generate_config: GenerateConfig
    tools: ToolRegistry | None = None
    max_tool_steps: int = 8
    tool_observer: Callable[[str, str], None] | None = None
    cancel_checker: Callable[[], bool] | None = None
    context_manager: ContextManager | None = None
    store: ConversationStore | None = None
    messages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.messages:
            system_prompt = DEFAULT_SYSTEM_PROMPT
            tool_block = ""
            if self.tools is not None:
                tool_block = self.tools.prompt_block()
            if tool_block:
                system_prompt = f"{system_prompt}\n\n{tool_block}"
            self.messages.append({"role": "system", "content": system_prompt})
            if self.store is not None:
                self.store.append_message(self.messages[-1])

    def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        if self.store is not None:
            self.store.append_message(self.messages[-1])
        for _ in range(self.max_tool_steps + 1):
            if self._canceled():
                return "Stopped: canceled."
            generation_messages = self.messages
            if self.context_manager is not None:
                generation_messages = self.context_manager.fit(self.messages)
            if self.tools is not None and self.backend.supports_native_tools:
                response = self.backend.generate_with_tools(
                    generation_messages,
                    self.generate_config,
                    self.tools.specs(),
                )
            else:
                response = self.backend.generate(generation_messages, self.generate_config)
            if self._canceled():
                return "Stopped: canceled."
            self.messages.append({"role": "assistant", "content": response.text})
            if self.store is not None:
                self.store.append_message(self.messages[-1])
            call = parse_tool_call(response.text)
            if call is None or self.tools is None:
                return response.text
            if self.tool_observer is not None:
                self.tool_observer("call", f"{call.name}({call.arguments})")
            if self._canceled():
                return "Stopped: canceled."
            result = self.tools.run(call.name, call.arguments)
            if self.tool_observer is not None:
                self.tool_observer("result", result.content)
            tool_message = {
                "role": "tool",
                "content": observation_message(call, result.ok, result.content),
            }
            self.messages.append(tool_message)
            if self.store is not None:
                self.store.append_message(tool_message)
        return "Stopped: tool step limit reached."

    def stream_ask(self, prompt: str):
        if self.tools is None:
            self.messages.append({"role": "user", "content": prompt})
            if self.store is not None:
                self.store.append_message(self.messages[-1])
            parts: list[str] = []
            generation_messages = self.messages
            if self.context_manager is not None:
                generation_messages = self.context_manager.fit(self.messages)
            for chunk in self.backend.stream(generation_messages, self.generate_config):
                if self._canceled():
                    yield "Stopped: canceled."
                    return
                parts.append(chunk)
                yield chunk
            self.messages.append({"role": "assistant", "content": "".join(parts)})
            if self.store is not None:
                self.store.append_message(self.messages[-1])
            return

        yield self.ask(prompt)

    def _canceled(self) -> bool:
        return bool(self.cancel_checker and self.cancel_checker())
