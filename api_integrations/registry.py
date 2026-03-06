"""
api_integrations/registry.py
Stores and manages user-configured external API integrations.
Each integration exposes itself as a "tool" that agents can invoke.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class IntegrationAuth(BaseModel):
    """Authentication config for an external API."""
    type: str = "api_key"           # api_key | bearer | basic | none
    header_name: str = "Authorization"
    api_key: Optional[str] = None
    prefix: str = "Bearer"          # prefix before key in header


class UserIntegration(BaseModel):
    """A single user-configured external API integration."""
    id: str
    name: str
    description: str                # Shown to LLM as tool description
    base_url: str
    method: str = "GET"             # HTTP method
    path_template: str = "/"        # e.g. "/search?q={query}"
    auth: Optional[IntegrationAuth] = None
    extra_headers: dict[str, str] = {}
    enabled: bool = True
    # Parameter schema shown to the LLM so it knows what to pass
    parameters: dict[str, Any] = {}


class IntegrationRegistry:
    """
    In-memory registry of user-defined API integrations.
    In production this would be persisted to a DB.
    """

    # Built-in integrations available to all users
    BUILTIN: list[UserIntegration] = [
        UserIntegration(
            id="web_search",
            name="Web Search",
            description="Search the web for current information using a search query.",
            base_url="https://api.duckduckgo.com",
            method="GET",
            path_template="/?q={query}&format=json&no_html=1&skip_disambig=1",
            parameters={"query": {"type": "string", "description": "Search query"}},
        ),
        UserIntegration(
            id="weather",
            name="Weather",
            description="Get current weather for a city.",
            base_url="https://wttr.in",
            method="GET",
            path_template="/{city}?format=j1",
            parameters={"city": {"type": "string", "description": "City name"}},
        ),
    ]

    def __init__(self):
        # Start with built-ins; users can add more via the API
        self._store: dict[str, UserIntegration] = {
            i.id: i for i in self.BUILTIN
        }

    def list(self) -> list[UserIntegration]:
        return list(self._store.values())

    def get(self, integration_id: str) -> Optional[UserIntegration]:
        return self._store.get(integration_id)

    def add(self, integration: UserIntegration) -> UserIntegration:
        self._store[integration.id] = integration
        logger.info("Integration registered: %s (%s)", integration.id, integration.base_url)
        return integration

    def remove(self, integration_id: str) -> bool:
        if integration_id in self._store:
            del self._store[integration_id]
            return True
        return False

    def to_tool_definitions(self) -> list[dict]:
        """
        Convert enabled integrations into Anthropic-style tool definitions
        so the controller can pass them to agents.
        """
        tools = []
        for integ in self._store.values():
            if not integ.enabled:
                continue
            tools.append({
                "name": integ.id,
                "description": integ.description,
                "input_schema": {
                    "type": "object",
                    "properties": integ.parameters,
                    "required": list(integ.parameters.keys()),
                },
            })
        return tools

    def to_prompt_context(self) -> str:
        """Plain-text summary of available tools for injection into prompts."""
        enabled = [i for i in self._store.values() if i.enabled]
        if not enabled:
            return ""
        lines = ["## Available External Tools", "You may reference results from these APIs:"]
        for integ in enabled:
            lines.append(f"- **{integ.name}** (`{integ.id}`): {integ.description}")
        return "\n".join(lines)
