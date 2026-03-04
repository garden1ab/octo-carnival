"""
api_clients/openai_client.py — OpenAI (and OpenAI-compatible) API wrapper.

Works with:
  • OpenAI official API  (base_url=None)
  • Azure OpenAI         (set base_url to your Azure endpoint)
  • Local Ollama / LM Studio / vLLM  (set base_url + dummy api_key)
  • Any other OpenAI-compatible endpoint

Uses the `openai` Python SDK's AsyncOpenAI client.
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """
    Wrapper around OpenAI Chat Completions API.
    Setting `base_url` redirects to any OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 60,
        max_retries: int = 3,
        provider_label: str = "openai",
    ):
        super().__init__(
            provider=provider_label,
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
        client_kwargs: dict = {
            "api_key": api_key or "sk-no-key",  # local servers may not need a real key
            "timeout": float(timeout),
        }
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = AsyncOpenAI(**client_kwargs)

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.provider,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason or "stop",
            raw=response.model_dump(),
        )
