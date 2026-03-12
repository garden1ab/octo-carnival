"""
system_settings.py — Runtime-mutable system settings.

Stores:
  • Controller LLM config  (provider, model, api_key, base_url, temperature, etc.)
  • Global agent system prompt  (prepended to every worker agent's system message)
  • Per-role system prompt overrides
  • Decompose / synthesis prompt overrides

All changes take effect on the NEXT request — no restart needed.
"""

from __future__ import annotations

import logging
from typing import Optional
from pydantic import BaseModel

from config import ControllerConfig

logger = logging.getLogger(__name__)

# ── Default prompts (mirrors controller.py constants) ──────────────────────────
DEFAULT_DECOMPOSE_SYSTEM = (
    "You are the orchestration controller of a multi-agent AI system.\n"
    "Break the user's request into focused sub-tasks, one per available agent.\n\n"
    "Available agents:\n{agent_descriptions}\n\n"
    "Respond ONLY with a valid JSON array. Each element:\n"
    '  - "agent_id"    : string  — must be from the list above\n'
    '  - "role"        : string  — researcher | summarizer | analyst | writer | critic | coder | general\n'
    '  - "instruction" : string  — specific self-contained instruction for the agent\n'
    '  - "needs_docs"  : boolean — whether to receive uploaded documents\n\n'
    "Output ONLY the JSON array, nothing else."
)

DEFAULT_SYNTHESIS_SYSTEM = (
    "You are the synthesis controller. Combine multiple agent outputs into one\n"
    "cohesive, high-quality final answer. Do not mention agents or orchestration.\n"
    "Format in clear markdown."
)

DEFAULT_AGENT_SYSTEM = (
    "Respond only with the content requested. "
    "Be concise unless depth is required. "
    "Format responses in clear markdown."
)

DEFAULT_ROLE_PROMPTS: dict[str, str] = {
    "researcher": "You are a meticulous researcher. Gather facts, cite sources when possible, and be thorough.",
    "summarizer": "You are a precise summarizer. Condense information clearly without losing key details.",
    "analyst":    "You are a critical analyst. Examine data, spot patterns, and provide structured insights.",
    "writer":     "You are a skilled writer. Produce clear, engaging, well-structured content.",
    "critic":     "You are a constructive critic. Identify weaknesses, inconsistencies, and areas for improvement.",
    "coder":      "You are an expert software engineer. Write clean, well-commented, production-ready code.",
    "general":    "You are a helpful, knowledgeable assistant.",
}


# ── Pydantic models for the API ────────────────────────────────────────────────

class ControllerSettings(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: Optional[str] = None
    api_key: Optional[str] = None          # write-only; masked in GET
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 120
    max_retries: int = 3


class PromptSettings(BaseModel):
    """All editable system prompts."""
    # Controller prompts
    decompose_system: str = DEFAULT_DECOMPOSE_SYSTEM
    synthesis_system: str = DEFAULT_SYNTHESIS_SYSTEM
    # Global suffix appended to every worker agent's system message
    global_agent_system: str = DEFAULT_AGENT_SYSTEM
    # Per-role overrides  (role name → full prompt; empty string = use default)
    role_prompts: dict[str, str] = DEFAULT_ROLE_PROMPTS.copy()


class SystemSettingsResponse(BaseModel):
    controller: ControllerSettings
    prompts: PromptSettings


# ── Settings store ─────────────────────────────────────────────────────────────

class SystemSettings:
    """
    In-memory mutable settings.  The controller and worker agents read from
    this object on every call, so changes are reflected immediately.
    """

    def __init__(self, initial_controller: ControllerConfig):
        self._controller = ControllerSettings(
            provider=initial_controller.provider,
            model=initial_controller.model,
            base_url=initial_controller.base_url,
            api_key=initial_controller.api_key,
            max_tokens=initial_controller.max_tokens,
            temperature=initial_controller.temperature,
            timeout=initial_controller.timeout,
            max_retries=initial_controller.max_retries,
        )
        self._prompts = PromptSettings()

    # ── Controller ─────────────────────────────────────────────────────────

    @property
    def controller(self) -> ControllerSettings:
        return self._controller

    def update_controller(self, update: ControllerSettings) -> ControllerSettings:
        # Preserve existing API key if the new one is masked or empty
        if not update.api_key or update.api_key == "***":
            update.api_key = self._controller.api_key
        self._controller = update
        logger.info("Controller updated → %s / %s", update.provider, update.model)
        return self._controller

    def controller_as_config(self) -> ControllerConfig:
        c = self._controller
        return ControllerConfig(
            provider=c.provider,
            model=c.model,
            base_url=c.base_url,
            api_key=c.api_key,
            max_tokens=c.max_tokens,
            temperature=c.temperature,
            timeout=c.timeout,
            max_retries=c.max_retries,
        )

    # ── Prompts ────────────────────────────────────────────────────────────

    @property
    def prompts(self) -> PromptSettings:
        return self._prompts

    def update_prompts(self, update: PromptSettings) -> PromptSettings:
        self._prompts = update
        logger.info("Prompt settings updated")
        return self._prompts

    def reset_prompts(self) -> PromptSettings:
        self._prompts = PromptSettings()
        logger.info("Prompt settings reset to defaults")
        return self._prompts

    # ── Safe GET response (masks API key) ──────────────────────────────────

    def to_response(self) -> SystemSettingsResponse:
        ctrl = self._controller.model_copy()
        if ctrl.api_key:
            ctrl.api_key = "***"
        return SystemSettingsResponse(controller=ctrl, prompts=self._prompts)
