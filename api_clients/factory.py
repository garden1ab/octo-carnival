"""
api_clients/factory.py — Build the correct BaseLLMClient from an AgentConfig.
"""

from __future__ import annotations

import logging
from config import AgentConfig, ControllerConfig
from api_clients.base import BaseLLMClient

logger = logging.getLogger(__name__)


def build_client(cfg: AgentConfig | ControllerConfig) -> BaseLLMClient:
    """
    Instantiate the right API client based on `cfg.provider`.

    Supported providers
    -------------------
    "anthropic"      → AnthropicClient
    "openai"         → OpenAIClient (official OpenAI)
    "openai_compat"  → OpenAIClient pointed at a custom base_url
    "local"          → LocalModelClient (Ollama / LM Studio / vLLM)
    """
    provider = cfg.provider.lower()

    if provider == "anthropic":
        from api_clients.anthropic_client import AnthropicClient
        if not cfg.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        return AnthropicClient(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
        )

    if provider in ("openai", "openai_compat"):
        from api_clients.openai_client import OpenAIClient
        if not cfg.api_key and provider == "openai":
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        return OpenAIClient(
            api_key=cfg.api_key or "sk-no-key",
            model=cfg.model,
            base_url=cfg.base_url,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
            provider_label=provider,
        )

    if provider == "local":
        from api_clients.local_client import LocalModelClient
        return LocalModelClient(
            model=cfg.model,
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
        )

    raise ValueError(
        f"Unknown provider '{cfg.provider}'. "
        "Supported: anthropic | openai | openai_compat | local"
    )
