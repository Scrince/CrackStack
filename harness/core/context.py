from __future__ import annotations

from dataclasses import dataclass

from harness.backends.base import Message


@dataclass(frozen=True)
class ContextManager:
    context_window: int
    reserve_tokens: int = 512

    def estimate_tokens(self, messages: list[Message]) -> int:
        return sum(max(1, len(message.get("content", "")) // 4) + 4 for message in messages)

    def fit(self, messages: list[Message]) -> list[Message]:
        if self.context_window <= 0:
            return messages
        budget = max(256, self.context_window - self.reserve_tokens)
        if self.estimate_tokens(messages) <= budget:
            return messages
        if not messages:
            return messages

        system = messages[0] if messages[0].get("role") == "system" else None
        tail = messages[1:] if system else messages[:]
        anchor = next((message for message in tail if message.get("role") == "user"), None)
        trim_tail = tail[:]
        if anchor is not None:
            trim_tail.remove(anchor)
        kept: list[Message] = []

        prefix = ([system] if system else []) + ([anchor] if anchor else [])
        insert_at = len(prefix)
        for message in reversed(trim_tail):
            candidate = prefix + kept
            candidate.insert(insert_at, message)
            if self.estimate_tokens(candidate) > budget and kept:
                break
            kept.insert(0, message)

        dropped = len(tail) - len(kept) - (1 if anchor else 0)
        if dropped > 0:
            summary = {
                "role": "system",
                "content": f"Context manager dropped {dropped} older message(s) to fit the model window.",
            }
            return ([system] if system else []) + ([anchor] if anchor else []) + [summary] + kept
        return prefix + kept
