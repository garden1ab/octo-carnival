"""
mcp/registry.py — Registry of MCP servers.

Manages connect/disconnect lifecycle, provides tool definitions in the
same format as IntegrationRegistry.to_tool_definitions() so the tool
executor can route to either system transparently.

Env-based config (loaded at startup):
  MCP_1_ID=brave-search
  MCP_1_NAME=Brave Search
  MCP_1_URL=https://brave-search.mcp.run/sse
  MCP_1_API_KEY=your-key
  MCP_1_TRANSPORT=sse
  MCP_2_ID=...
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from mcp.client import MCPClient, MCPServerConfig, MCPTool

logger = logging.getLogger(__name__)


class MCPRegistry:
    """In-memory registry of MCP server connections."""

    def __init__(self):
        self._servers: dict[str, MCPClient] = {}
        # Map: tool_name → server_id  (populated after connect)
        self._tool_server_map: dict[str, str] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def add_server(self, config: MCPServerConfig) -> MCPClient:
        client = MCPClient(config)
        self._servers[config.id] = client
        logger.info("MCP server registered: %s (%s)", config.id, config.url)
        return client

    def remove_server(self, server_id: str) -> bool:
        if server_id not in self._servers:
            return False
        # Remove tool mappings for this server
        self._tool_server_map = {
            k: v for k, v in self._tool_server_map.items() if v != server_id
        }
        del self._servers[server_id]
        return True

    async def connect_all(self):
        """Connect all registered servers concurrently."""
        if not self._servers:
            return
        tasks = [self._connect_one(sid, client) for sid, client in self._servers.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def connect_server(self, server_id: str) -> bool:
        client = self._servers.get(server_id)
        if not client:
            return False
        return await self._connect_one(server_id, client)

    async def _connect_one(self, server_id: str, client: MCPClient) -> bool:
        try:
            ok = await client.connect()
            if ok:
                # Register tool → server mapping
                for tool in client.tools:
                    qualified = f"{server_id}__{tool.name}"
                    self._tool_server_map[qualified] = server_id
                    # Also register bare name (first server wins for conflicts)
                    if tool.name not in self._tool_server_map:
                        self._tool_server_map[tool.name] = server_id
            return ok
        except Exception as exc:
            logger.error("Failed to connect MCP server %s: %s", server_id, exc)
            return False

    async def disconnect_all(self):
        for client in self._servers.values():
            await client.disconnect()
        self._tool_server_map.clear()

    # ── Tool discovery ─────────────────────────────────────────────────────

    def to_tool_definitions(self) -> list[dict]:
        """
        Return all tools from all connected MCP servers in the standard
        tool-definition format used by the tool loop.
        
        Tool names are prefixed with server_id__ to avoid collisions.
        The bare name is also registered as an alias (first-server wins).
        """
        defs = []
        seen_bare: set[str] = set()

        for server_id, client in self._servers.items():
            if not client.is_connected or not client.config.enabled:
                continue
            for tool in client.tools:
                # Qualified name always included
                qualified = f"{server_id}__{tool.name}"
                defs.append({
                    "name": qualified,
                    "description": f"[{client.config.name}] {tool.description}",
                    "input_schema": tool.input_schema,
                })
                # Bare name as alias (first server to register wins)
                if tool.name not in seen_bare:
                    seen_bare.add(tool.name)
                    defs.append({
                        "name": tool.name,
                        "description": f"[{client.config.name}] {tool.description}",
                        "input_schema": tool.input_schema,
                    })
        return defs

    def find_server_for_tool(self, tool_name: str) -> Optional[MCPClient]:
        """Given a tool name (bare or qualified), return the owning client."""
        server_id = self._tool_server_map.get(tool_name)
        if server_id:
            return self._servers.get(server_id)
        # Try stripping server prefix (server_id__tool_name)
        if "__" in tool_name:
            sid, bare = tool_name.split("__", 1)
            return self._servers.get(sid)
        return None

    def get_bare_tool_name(self, tool_name: str) -> str:
        """Strip server prefix if present."""
        if "__" in tool_name:
            return tool_name.split("__", 1)[1]
        return tool_name

    # ── Introspection ──────────────────────────────────────────────────────

    def list_servers(self) -> list[dict]:
        return [
            {
                "id": sid,
                "name": c.config.name,
                "url": c.config.url,
                "transport": c.config.transport,
                "enabled": c.config.enabled,
                "connected": c.is_connected,
                "tool_count": len(c.tools),
                "tools": [t.name for t in c.tools],
                "description": c.config.description,
            }
            for sid, c in self._servers.items()
        ]

    def get_server(self, server_id: str) -> Optional[MCPClient]:
        return self._servers.get(server_id)


def load_mcp_servers_from_env() -> list[MCPServerConfig]:
    """
    Read MCP_N_* env vars and return a list of server configs.
    
    MCP_1_ID=brave-search
    MCP_1_NAME=Brave Search
    MCP_1_URL=https://brave-search.mcp.run/sse
    MCP_1_API_KEY=bsa_...
    MCP_1_TRANSPORT=sse          (optional, default: sse)
    MCP_1_DESCRIPTION=...        (optional)
    MCP_1_ENABLED=true           (optional, default: true)
    """
    configs = []
    idx = 1
    while True:
        prefix = f"MCP_{idx}_"
        server_id = os.getenv(f"{prefix}ID")
        if not server_id:
            break
        url = os.getenv(f"{prefix}URL")
        if not url:
            logger.warning("MCP_%d_URL not set, skipping server %s", idx, server_id)
            idx += 1
            continue
        configs.append(MCPServerConfig(
            id=server_id,
            name=os.getenv(f"{prefix}NAME", server_id),
            url=url,
            transport=os.getenv(f"{prefix}TRANSPORT", "sse"),
            api_key=os.getenv(f"{prefix}API_KEY"),
            enabled=os.getenv(f"{prefix}ENABLED", "true").lower() != "false",
            description=os.getenv(f"{prefix}DESCRIPTION", ""),
        ))
        idx += 1
    return configs
