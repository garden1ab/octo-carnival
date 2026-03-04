"""
api_clients/local_client.py — Client for local model servers (Ollama, LM Studio, vLLM).

Uses plain httpx (async) so there is no dependency on a specific SDK.
Expects an OpenAI-compatible /v1/chat/completions endpoint.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

_DEFAULT_LOCAL_URL = "http://localhost:11434/v1"  # Ollama default


class LocalModelClient(BaseLLMClient):
    """
    Thin async HTTP client for any local OpenAI-compatible model server.

    Usage example (Ollama):
        client = LocalModelClient(model="llama3", base_url="http://localhost:11434/v1")
    """

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = _DEFAULT_LOCAL_URL,
        api_key: Optional[str] = "local",   # dummy key; most local servers ignore it
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: int = 120,                  # local models can be slow
        max_retries: int = 2,
    ):
        super().__init__(
            provider="local",
            model=model,
            api_key=api_key,
            base_url=base_url or _DEFAULT_LOCAL_URL,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._base_url = (base_url or _DEFAULT_LOCAL_URL).rstrip("/")

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key or 'local'}"},
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"] or "",
            model=data.get("model", self.model),
            provider="local",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )
