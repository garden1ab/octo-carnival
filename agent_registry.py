"""
agent_registry.py — Runtime agent management.

Allows agents to be added, updated, and removed via the API without restarting.
The MainController polls this registry so changes take effect immediately.
"""

from __future__ import annotations

import logging
from typing import Optional
from pydantic import BaseModel

from config import AgentConfig
from api_clients import build_client
from agents.worker import WorkerAgent

logger = logging.getLogger(__name__)


class AgentDefinition(BaseModel):
    """API-facing agent definition (no secrets logged)."""
    agent_id: str
    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None      # write-only; never returned in GET
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 60
    max_retries: int = 3

    def to_config(self) -> AgentConfig:
        return AgentConfig(
            agent_id=self.agent_id,
            provider=self.provider,
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def safe_dict(self) -> dict:
        """Return definition without the api_key for API responses."""
        d = self.model_dump()
        if d.get("api_key"):
            d["api_key"] = "***"
        return d


class AgentRegistry:
    """
    In-memory registry of live WorkerAgents.
    The controller reads _agents directly so hot-adds/removes are instant.
    """

    def __init__(self):
        self._agents: dict[str, WorkerAgent] = {}
        self._definitions: dict[str, AgentDefinition] = {}

    # ── Read ────────────────────────────────────────────────────────────────

    @property
    def agents(self) -> dict[str, WorkerAgent]:
        return self._agents

    def list_definitions(self) -> list[dict]:
        return [d.safe_dict() for d in self._definitions.values()]

    def get_definition(self, agent_id: str) -> Optional[AgentDefinition]:
        return self._definitions.get(agent_id)

    # ── Write ───────────────────────────────────────────────────────────────

    def add_or_update(self, defn: AgentDefinition) -> dict:
        cfg = defn.to_config()
        try:
            client = build_client(cfg)
            worker = WorkerAgent(cfg, client)
            self._agents[defn.agent_id] = worker
            self._definitions[defn.agent_id] = defn
            logger.info("Agent '%s' registered (%s / %s)", defn.agent_id, defn.provider, defn.model)
            return defn.safe_dict()
        except Exception as exc:
            raise ValueError(f"Failed to build agent '{defn.agent_id}': {exc}") from exc

    def remove(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            del self._definitions[agent_id]
            logger.info("Agent '%s' removed", agent_id)
            return True
        return False

    def seed_from_config(self, agent_configs: list[AgentConfig]) -> None:
        """Populate registry from startup config (env vars)."""
        for cfg in agent_configs:
            defn = AgentDefinition(
                agent_id=cfg.agent_id,
                provider=cfg.provider,
                model=cfg.model,
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                timeout=cfg.timeout,
                max_retries=cfg.max_retries,
            )
            try:
                self.add_or_update(defn)
            except Exception as exc:
                logger.error("Skipping agent '%s' at startup: %s", cfg.agent_id, exc)
