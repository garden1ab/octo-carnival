"""
api_clients/anthropic_client.py — Anthropic Claude with native tool_use support.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import anthropic

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001",
                 base_url: Optional[str] = None, max_tokens: int = 2048,
                 temperature: float = 0.7, timeout: int = 60, max_retries: int = 3):
        super().__init__("anthropic", model, api_key, base_url, max_tokens, temperature, timeout, max_retries)
        kwargs: dict = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)

    def _split_messages(self, messages: list[LLMMessage]):
        system_parts = [m.content for m in messages if m.role == "system"]
        system = "\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN
        convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return system, convo

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        system, convo = self._split_messages(messages)
        if not convo:
            raise ValueError("No user/assistant messages provided")
        resp = await self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            temperature=self.temperature, system=system, messages=convo,
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return LLMResponse(
            content=text, model=resp.model, provider="anthropic",
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            finish_reason=resp.stop_reason or "stop", raw=resp.model_dump(),
        )

    async def _complete_with_tools_impl(
        self, messages: list[LLMMessage], tools: list[dict]
    ) -> LLMResponse:
        """Use Anthropic's native tool_use API."""
        system, convo = self._split_messages(messages)
        if not convo:
            raise ValueError("No user/assistant messages provided")

        # Convert our generic tool schema to Anthropic format
        anthropic_tools = [
            {"name": t["name"], "description": t.get("description", ""),
             "input_schema": t.get("input_schema", {"type": "object", "properties": {}})}
            for t in tools
        ]

        resp = await self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            temperature=self.temperature, system=system,
            messages=convo, tools=anthropic_tools,
        )

        # Extract text and tool_use blocks
        text_parts = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    call_id=block.id,
                    name=block.name,
                    arguments=dict(block.input) if block.input else {},
                ))

        finish = resp.stop_reason or "stop"
        if tool_calls:
            finish = "tool_use"

        return LLMResponse(
            content="".join(text_parts), model=resp.model, provider="anthropic",
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            finish_reason=finish, tool_calls=tool_calls, raw=resp.model_dump(),
        )

    def build_tool_result_messages(
        self, original_messages: list[LLMMessage],
        assistant_raw: Any, tool_results: list
    ) -> list[dict]:
        """
        Build the Anthropic-format messages list that includes the assistant's
        tool_use blocks and the corresponding tool_result blocks.
        Used by ToolLoop when continuing after a tool call.
        """
        # Reconstruct the assistant message with full content blocks
        asst_content = assistant_raw.get("content", []) if assistant_raw else []

        system_parts = [m.content for m in original_messages if m.role == "system"]
        convo = [{"role": m.role, "content": m.content}
                 for m in original_messages if m.role != "system"]

        # Append the assistant's response (with tool_use blocks)
        convo.append({"role": "assistant", "content": asst_content})

        # Append tool results
        tool_result_content = [
            {"type": "tool_result", "tool_use_id": tr.call_id, "content": tr.content}
            for tr in tool_results
        ]
        convo.append({"role": "user", "content": tool_result_content})

        return convo
