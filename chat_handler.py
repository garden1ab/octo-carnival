"""
chat_handler.py — Simple single-turn and multi-turn chat with a chosen agent/model.

Bypasses the orchestrator entirely — just: user message → LLM → response.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from pydantic import BaseModel

from api_clients import LLMMessage, build_client
from config import AgentConfig

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str        # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    agent_id: Optional[str] = None   # if set, use that agent's config
    # Inline model override (used when user picks a model directly)
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0


class ChatHandler:
    def __init__(self, agent_registry):
        self._registry = agent_registry

    async def chat(self, req: ChatRequest) -> ChatResponse:
        start = time.monotonic()

        # Build the LLM client
        if req.agent_id and req.agent_id in self._registry.agents:
            # Use an existing registered agent's client
            worker = self._registry.agents[req.agent_id]
            client = worker.client
        elif req.provider and req.model:
            # Build an ad-hoc client from the request params
            cfg = AgentConfig(
                agent_id="chat-adhoc",
                provider=req.provider,
                model=req.model,
                api_key=req.api_key,
                base_url=req.base_url,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            client = build_client(cfg)
        else:
            # Fall back to first available agent
            if not self._registry.agents:
                raise ValueError("No agents available for chat")
            client = next(iter(self._registry.agents.values())).client

        # Build message list
        msgs: list[LLMMessage] = []
        if req.system_prompt:
            msgs.append(LLMMessage(role="system", content=req.system_prompt))
        for m in req.messages:
            msgs.append(LLMMessage(role=m.role, content=m.content))

        response = await client.complete(msgs)
        duration = time.monotonic() - start

        return ChatResponse(
            content=response.content,
            model=response.model,
            provider=response.provider,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_seconds=duration,
        )
