"""
api_clients/local_client.py — Ollama / LM Studio / vLLM.

Tries native OpenAI-compatible tool calling first; falls back to
the JSON prompt-engineering method if the model doesn't support it.
The fallback works with any text model that can follow instructions.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

_DEFAULT_LOCAL_URL = "http://localhost:11434/v1"


class LocalModelClient(BaseLLMClient):
    def __init__(self, model: str = "llama3", base_url: str = _DEFAULT_LOCAL_URL,
                 api_key: Optional[str] = "local", max_tokens: int = 2048,
                 temperature: float = 0.7, timeout: int = 120, max_retries: int = 2):
        super().__init__("local", model, api_key, base_url or _DEFAULT_LOCAL_URL,
                         max_tokens, temperature, timeout, max_retries)
        self._base = (base_url or _DEFAULT_LOCAL_URL).rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key or 'local'}"}

    async def _post(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self._base}/chat/completions",
                                  json=payload, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        data = await self._post({
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        })
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"] or "",
            model=data.get("model", self.model), provider="local",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"), raw=data,
        )

    async def _complete_with_tools_impl(
        self, messages: list[LLMMessage], tools: list[dict]
    ) -> LLMResponse:
        """
        Try native OpenAI-compatible tool calling (works on llama3.1, qwen2.5, mistral-nemo).
        If the server rejects tool params or returns no tool_calls, fall back to
        prompt-engineering extraction.
        """
        oai_tools = [
            {"type": "function", "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            }}
            for t in tools
        ]
        try:
            data = await self._post({
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": False,
                "tools": oai_tools,
                "tool_choice": "auto",
            })
            choice = data["choices"][0]
            usage = data.get("usage", {})
            msg = choice.get("message", {})
            tool_calls: list[ToolCall] = []

            for tc in msg.get("tool_calls") or []:
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except (json.JSONDecodeError, KeyError):
                    args = {}
                tool_calls.append(ToolCall(
                    call_id=tc.get("id", f"local-{len(tool_calls)}"),
                    name=tc["function"]["name"],
                    arguments=args,
                ))

            if tool_calls:
                return LLMResponse(
                    content=msg.get("content") or "",
                    model=data.get("model", self.model), provider="local",
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    finish_reason="tool_use", tool_calls=tool_calls, raw=data,
                )
        except Exception as exc:
            logger.info("[local/%s] native tool calling failed (%s) — using JSON fallback", self.model, exc)

        # ── JSON prompt-engineering fallback ─────────────────────────────
        logger.info("[local/%s] using <tool_call> JSON fallback", self.model)
        return await super()._complete_with_tools_impl(messages, tools)
