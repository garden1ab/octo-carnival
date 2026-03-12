"""
api_clients/openai_client.py — OpenAI (and OpenAI-compatible) with native function calling.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: Optional[str] = None, max_tokens: int = 2048,
                 temperature: float = 0.7, timeout: int = 60,
                 max_retries: int = 3, provider_label: str = "openai"):
        super().__init__(provider_label, model, api_key, base_url, max_tokens, temperature, timeout, max_retries)
        self._client = AsyncOpenAI(
            api_key=api_key or "sk-no-key",
            timeout=float(timeout),
            **({"base_url": base_url} if base_url else {}),
        )

    def _build_oai_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self.model, messages=self._build_oai_messages(messages),
            max_tokens=self.max_tokens, temperature=self.temperature,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            content=choice.message.content or "", model=resp.model, provider=self.provider,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop", raw=resp.model_dump(),
        )

    async def _complete_with_tools_impl(
        self, messages: list[LLMMessage], tools: list[dict]
    ) -> LLMResponse:
        """Use OpenAI's native function calling (tool_choice='auto')."""
        # Convert to OpenAI tools format
        oai_tools = [
            {"type": "function", "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            }}
            for t in tools
        ]
        try:
            resp = await self._client.chat.completions.create(
                model=self.model, messages=self._build_oai_messages(messages),
                max_tokens=self.max_tokens, temperature=self.temperature,
                tools=oai_tools, tool_choice="auto",
            )
        except Exception as exc:
            # Model may not support tools (e.g. some local OpenAI-compat servers)
            # Fall back to text-based tool injection
            logger.warning("[%s] native tools failed (%s), using JSON fallback", self.model, exc)
            return await super()._complete_with_tools_impl(messages, tools)

        choice = resp.choices[0]
        usage = resp.usage
        tool_calls: list[ToolCall] = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    call_id=tc.id, name=tc.function.name, arguments=args
                ))

        finish = choice.finish_reason or "stop"
        if tool_calls:
            finish = "tool_use"

        return LLMResponse(
            content=choice.message.content or "", model=resp.model, provider=self.provider,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=finish, tool_calls=tool_calls, raw=resp.model_dump(),
        )
