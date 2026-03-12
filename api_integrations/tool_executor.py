"""
api_integrations/tool_executor.py — Unified tool executor.

Routes tool calls to:
  1. DocDBRegistry  — document database tools  ({id}_list, {id}_get, {id}_search)
  2. IntegrationRegistry — single-endpoint HTTP APIs
  3. MCPRegistry    — MCP server tools

Priority: DocDB > HTTP integrations > MCP
(DocDB tools have structured names that won't collide with others.)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

import httpx

from api_integrations.registry import IntegrationRegistry, UserIntegration

if TYPE_CHECKING:
    from mcp.registry import MCPRegistry
    from api_integrations.docdb import DocDBRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(
        self,
        integration_registry: IntegrationRegistry,
        mcp_registry: Optional["MCPRegistry"] = None,
        docdb_registry: Optional["DocDBRegistry"] = None,
        timeout: int = 20,
    ):
        self._integrations = integration_registry
        self._mcp = mcp_registry
        self._docdb = docdb_registry
        self.timeout = timeout

    async def execute(self, tool_name: str, params: dict[str, Any]) -> str:
        # ── DocDB tools  ({db_id}_list / _get / _search) ──────────────────
        if self._docdb:
            match = self._docdb.find_for_tool(tool_name)
            if match:
                db, operation = match
                if not db.enabled:
                    return f"[Document database '{db.id}' is disabled]"
                from api_integrations.docdb_executor import DocDBExecutor
                logger.info("Routing '%s' → DocDB '%s' op=%s", tool_name, db.id, operation)
                return await DocDBExecutor(db).execute(operation, params)

        # ── MCP tools ──────────────────────────────────────────────────────
        if self._mcp:
            client = self._mcp.find_server_for_tool(tool_name)
            if client:
                bare = self._mcp.get_bare_tool_name(tool_name)
                logger.info("Routing '%s' → MCP '%s'", tool_name, client.config.id)
                return await client.call_tool(bare, params)

        # ── HTTP integrations ──────────────────────────────────────────────
        integ = self._integrations.get(tool_name)
        if integ:
            if not integ.enabled:
                return f"[Integration '{tool_name}' is disabled]"
            logger.info("Routing '%s' → HTTP integration", tool_name)
            try:
                return await self._call_http(integ, params)
            except Exception as exc:
                logger.error("HTTP tool '%s' failed: %s", tool_name, exc)
                return f"[Tool '{tool_name}' error: {exc}]"

        return (
            f"[Tool '{tool_name}' not found. Available: {self._available_tools()}]"
        )

    def _available_tools(self) -> str:
        tools = [i.id for i in self._integrations.list() if i.enabled]
        if self._docdb:
            for db in self._docdb.list():
                if db.enabled:
                    tools.extend(t["name"] for t in db.to_tool_definitions())
        if self._mcp:
            for srv in self._mcp.list_servers():
                if srv["connected"]:
                    tools.extend(f"{srv['id']}__{t}" for t in srv["tools"])
        return ", ".join(tools) if tools else "none"

    async def _call_http(self, integ: UserIntegration, params: dict[str, Any]) -> str:
        path = integ.path_template
        for key, val in params.items():
            path = path.replace(f"{{{key}}}", str(val))
        url = integ.base_url.rstrip("/") + path
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
                resp = await client.get(url, headers=headers)
            elif integ.method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=params)
            else:
                resp = await client.request(integ.method.upper(), url, headers=headers)
            resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        text = str(resp.json()) if "json" in ct else resp.text
        return text[:4000] + ("…" if len(text) > 4000 else "")
