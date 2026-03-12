"""
api_clients/base.py — Abstract base with unified tool-calling interface.

Every provider implements two methods:
  _complete_impl()            — plain text completion (existing)
  _complete_with_tools_impl() — completion that may return tool_call blocks

The base class exposes:
  complete()            — plain completion with retries
  complete_with_tools() — tool-aware completion with retries

ToolCall / ToolResult dataclasses are the provider-agnostic currency
used by tool_loop.py to drive the agentic execution loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """A single conversation turn."""
    role: str       # "system" | "user" | "assistant"
    content: str


@dataclass
class ToolCall:
    """A tool invocation requested by the LLM."""
    call_id: str            # provider-assigned ID (used to match the result)
    name: str               # integration / tool name
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """The result of executing a ToolCall, fed back to the LLM."""
    call_id: str
    name: str
    content: str            # stringified result from ToolExecutor


@dataclass
class LLMResponse:
    """Normalised response from any provider."""
    content: str            # text content (may be empty if tool_calls present)
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"  # "stop" | "tool_use" | "end_turn"
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Optional[dict] = field(default=None, repr=False)


class BaseLLMClient(ABC):
    """
    Abstract LLM client with tool-calling support.
    Subclasses must implement _complete_impl().
    Subclasses SHOULD override _complete_with_tools_impl() for native tool support;
    the default falls back to JSON-extraction mode.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

    # ── Public API ────────────────────────────────────────────────────────

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        return await self._with_retries(messages, tools=None)

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict],
    ) -> LLMResponse:
        """
        Send messages with tool definitions. Returns LLMResponse where
        finish_reason == "tool_use" and tool_calls is populated if the
        LLM wants to invoke a tool.
        """
        return await self._with_retries(messages, tools=tools)

    # ── Abstract ──────────────────────────────────────────────────────────

    @abstractmethod
    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        ...

    async def _complete_with_tools_impl(
        self, messages: list[LLMMessage], tools: list[dict]
    ) -> LLMResponse:
        """
        Default fallback: prompt-engineer tool definitions into the system
        message and parse JSON tool calls from the response text.
        Used by providers that don't support native function calling (e.g. Ollama).
        """
        from api_clients.tool_json_fallback import inject_tools_into_messages, extract_tool_calls_from_text
        augmented = inject_tools_into_messages(messages, tools)
        response = await self._complete_impl(augmented)
        tool_calls = extract_tool_calls_from_text(response.content)
        if tool_calls:
            response.tool_calls = tool_calls
            response.finish_reason = "tool_use"
        return response

    # ── Retry helper ──────────────────────────────────────────────────────

    async def _with_retries(
        self, messages: list[LLMMessage], tools: Optional[list[dict]]
    ) -> LLMResponse:
        last_exc: Exception = RuntimeError("Unknown error")
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = time.monotonic()
                if tools is not None:
                    response = await self._complete_with_tools_impl(messages, tools)
                else:
                    response = await self._complete_impl(messages)
                elapsed = time.monotonic() - t0
                logger.debug(
                    "[%s/%s] %.2fs  in=%d out=%d  tool_calls=%d",
                    self.provider, self.model, elapsed,
                    response.input_tokens, response.output_tokens,
                    len(response.tool_calls),
                )
                return response
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "[%s/%s] attempt %d/%d failed: %s — retry in %ds",
                    self.provider, self.model, attempt, self.max_retries, exc, wait,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"[{self.provider}/{self.model}] all {self.max_retries} attempts failed: {last_exc}"
        ) from last_exc
