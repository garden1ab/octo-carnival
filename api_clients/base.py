"""
api_clients/base.py — Abstract base class that every LLM provider wrapper must implement.

All provider wrappers share:
  • A unified `complete()` async method.
  • Automatic retry with exponential back-off via `_with_retries()`.
  • Consistent LLMMessage / LLMResponse data structures.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """A single message in a conversation turn."""
    role: str          # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """Normalised response returned by every provider wrapper."""
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    raw: Optional[dict] = field(default=None, repr=False)


class BaseLLMClient(ABC):
    """
    Abstract LLM client.  Subclass this for each provider and implement
    `_complete_impl()`.  Call `complete()` from outside; it handles retries.
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        """
        Send `messages` to the LLM and return a normalised LLMResponse.
        Retries up to `max_retries` times with exponential back-off.
        """
        return await self._with_retries(messages)

    # ------------------------------------------------------------------
    # Must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    async def _complete_impl(self, messages: list[LLMMessage]) -> LLMResponse:
        """Provider-specific completion logic."""
        ...

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    async def _with_retries(self, messages: list[LLMMessage]) -> LLMResponse:
        last_exc: Exception = RuntimeError("Unknown error")
        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.monotonic()
                response = await self._complete_impl(messages)
                elapsed = time.monotonic() - start
                logger.debug(
                    "[%s/%s] completed in %.2fs  in=%d out=%d",
                    self.provider, self.model, elapsed,
                    response.input_tokens, response.output_tokens,
                )
                return response
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt  # 2, 4, 8 …
                logger.warning(
                    "[%s/%s] attempt %d/%d failed: %s — retrying in %ds",
                    self.provider, self.model, attempt, self.max_retries, exc, wait,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"[{self.provider}/{self.model}] all {self.max_retries} attempts failed: {last_exc}"
        ) from last_exc
