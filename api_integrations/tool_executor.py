"""
api_integrations/tool_executor.py
Executes HTTP calls to user-configured integrations.
Called by agents when the LLM requests a tool invocation.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from api_integrations.registry import IntegrationRegistry, UserIntegration

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes a named integration tool and returns a result string."""

    def __init__(self, registry: IntegrationRegistry, timeout: int = 15):
        self.registry = registry
        self.timeout = timeout

    async def execute(self, tool_name: str, params: dict[str, Any]) -> str:
        """
        Call the named integration with the given parameters.
        Returns a string result suitable for injection into agent context.
        """
        integ = self.registry.get(tool_name)
        if not integ:
            return f"[Tool '{tool_name}' not found in registry]"

        try:
            return await self._call(integ, params)
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", tool_name, exc)
            return f"[Tool '{tool_name}' error: {exc}]"

    async def _call(self, integ: UserIntegration, params: dict[str, Any]) -> str:
        # Build URL by substituting params into path template
        path = integ.path_template
        for key, val in params.items():
            path = path.replace(f"{{{key}}}", str(val))

        url = integ.base_url.rstrip("/") + path

        # Build headers
        headers = dict(integ.extra_headers)
        if integ.auth and integ.auth.api_key:
            if integ.auth.type == "api_key":
                headers[integ.auth.header_name] = (
                    f"{integ.auth.prefix} {integ.auth.api_key}".strip()
                )
            elif integ.auth.type == "bearer":
                headers["Authorization"] = f"Bearer {integ.auth.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if integ.method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif integ.method.upper() == "POST":
                response = await client.post(url, headers=headers, json=params)
            else:
                response = await client.request(
                    integ.method.upper(), url, headers=headers
                )
            response.raise_for_status()

        # Try to return useful text
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            data = response.json()
            # Truncate large responses
            text = str(data)
            return text[:4000] + ("..." if len(text) > 4000 else "")
        return response.text[:4000]
