"""OpenAI-compatible tool-calling client.

The audit loop depends only on `complete()`. Any gateway that speaks Chat
Completions tool calls can sit behind this class.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict | None
    raw_arguments: str


@dataclass
class LLMResponse:
    content: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


class ContextTooLong(Exception):
    pass


class OpenAICompatible:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float | None = None,
        reasoning_effort: str = "",
        max_tokens: int = 32768,
    ):
        from openai import OpenAI

        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=600, max_retries=0)

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        import openai

        delay = 4.0
        for attempt in range(5):
            try:
                return self._once(messages, tools)
            except (openai.APIConnectionError, openai.APITimeoutError):
                if attempt == 4:
                    raise
            except openai.APIStatusError as exc:
                if _is_context_error(exc):
                    raise ContextTooLong(str(exc)) from exc
                if exc.status_code not in RETRYABLE_STATUS or attempt == 4:
                    raise
            time.sleep(delay)
            delay *= 2
        raise AssertionError("unreachable")

    def _once(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message
        calls: list[ToolCall] = []
        for tool_call in message.tool_calls or []:
            raw = tool_call.function.arguments or "{}"
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    parsed = None
            except json.JSONDecodeError:
                parsed = None
            calls.append(ToolCall(id=tool_call.id, name=tool_call.function.name, arguments=parsed, raw_arguments=raw))
        usage = response.usage
        details = getattr(usage, "completion_tokens_details", None)
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        return LLMResponse(
            content=message.content or "",
            reasoning=getattr(message, "reasoning_content", None) or "",
            tool_calls=calls,
            finish_reason=choice.finish_reason or "",
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            reasoning_tokens=int(getattr(details, "reasoning_tokens", 0) or 0),
            cached_tokens=int(getattr(prompt_details, "cached_tokens", 0) or getattr(usage, "prompt_cache_hit_tokens", 0) or 0),
        )


def _is_context_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("context length", "maximum context", "too long", "context_length", "max context"))


class RecordingLLM:
    """Append every response to a JSONL file so the run can be replayed offline."""

    def __init__(self, inner, path: Path, role: str):
        self.inner = inner
        self.path = path
        self.role = role
        self.model = getattr(inner, "model", "unknown")
        self.base_url = getattr(inner, "base_url", "")
        self.reasoning_effort = getattr(inner, "reasoning_effort", "")

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        response = self.inner.complete(messages, tools)
        row = {"role": self.role, "model": self.model, **asdict(response)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return response


class ReplayExhausted(RuntimeError):
    pass


class ReplayLLM:
    """Serve recorded responses in order. The loop is sequential, so call order is the only key needed."""

    def __init__(self, rows: list[dict], role: str, model: str = "replay"):
        self.rows = rows
        self.role = role
        self.model = model
        self.base_url = "replay"
        self.reasoning_effort = ""

    @staticmethod
    def load(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        if not self.rows:
            raise ReplayExhausted("recorded responses ran out; the replayed run diverged from the original")
        row = self.rows.pop(0)
        if row.get("role") != self.role:
            raise ReplayExhausted(f"expected a {self.role} response, recording has {row.get('role')}; the run diverged")
        calls = [ToolCall(**call) for call in row.get("tool_calls") or []]
        fields = {key: row[key] for key in LLMResponse.__dataclass_fields__ if key in row and key != "tool_calls"}
        return LLMResponse(tool_calls=calls, **fields)
