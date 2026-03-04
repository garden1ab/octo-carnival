"""
api_clients/anthropic_client.py — Anthropic Claude API wrapper.

Uses the `anthropic` Python SDK.  Supports system prompts, multi-turn
conversations, and configurable models / token limits.
"""

from __future__ import annotations

import logging
from typing import Optional

import anthropic

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    """Wrapper around the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        base_url: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        super().__init__(
            provider="anthropic",
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
        client_kwargs: dict = {"api_key": api_key, "timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
        # AsyncAnthropic for non-blocking calls
        self._client = anthropic.AsyncAnthropic(**client_kwargs)

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        # Anthropic separates system prompt from conversation turns
        system_parts = [m.content for m in messages if m.role == "system"]
        system_text = "\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN

        conversation = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        if not conversation:
            raise ValueError("No user/assistant messages provided")

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_text,
            messages=conversation,
        )

        content_text = "".join(
            block.text for block in response.content
            if hasattr(block, "text")
        )

        return LLMResponse(
            content=content_text,
            model=response.model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
            raw=response.model_dump(),
        )
