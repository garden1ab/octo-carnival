"""
mcp/client.py — Async MCP client.

Implements the MCP JSON-RPC protocol over HTTP+SSE (the standard transport).
On connect it:
  1. Opens the SSE endpoint to get a session URL
  2. Sends initialize + notifications/initialized
  3. Calls tools/list to discover available tools
  4. Exposes call_tool() for actual execution

Connection is lazy — it connects on first use and reconnects on failure.

Supports both MCP transport versions:
  - SSE transport (older): GET /sse  →  SSE stream + POST to session URL
  - Streamable HTTP (newer): POST /mcp  →  single endpoint, optional SSE response
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_INIT_TIMEOUT = 15.0
_CALL_TIMEOUT = 30.0
_RECONNECT_DELAY = 5.0


@dataclass
class MCPTool:
    """A single tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: dict


@dataclass 
class MCPServerConfig:
    """Configuration for a single MCP server."""
    id: str
    name: str
    url: str                              # Base URL  e.g. https://server.mcp.run/sse
    transport: str = "sse"               # "sse" | "http"
    api_key: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""


class MCPClient:
    """
    Async MCP client for a single server.
    Maintains a persistent SSE session and exposes discovered tools.
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session_url: Optional[str] = None
        self._tools: list[MCPTool] = []
        self._connected = False
        self._lock = asyncio.Lock()
        self._msg_id = 0
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def tools(self) -> list[MCPTool]:
        return list(self._tools)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _build_headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            h["Authorization"] = f"Bearer {self.config.api_key}"
        h.update(self.config.headers)
        return h

    # ── Connection ─────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect to the MCP server and discover tools. Returns True on success."""
        async with self._lock:
            if self._connected:
                return True
            try:
                if self.config.transport == "http":
                    return await self._connect_http()
                else:
                    return await self._connect_sse()
            except Exception as exc:
                logger.error("[MCP %s] connect failed: %s", self.config.id, exc)
                self._connected = False
                return False

    async def _connect_sse(self) -> bool:
        """SSE transport: GET /sse to get session URL, then POST JSON-RPC."""
        base = self.config.url.rstrip("/")
        sse_url = base if base.endswith("/sse") else f"{base}/sse"

        async with httpx.AsyncClient(timeout=_INIT_TIMEOUT) as client:
            # Open SSE connection — the first event gives us the session endpoint
            async with client.stream("GET", sse_url, headers=self._build_headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data.startswith("/"):
                            # Session endpoint path
                            self._session_url = f"{base.rsplit('/', 1)[0]}{data}"
                            break
                        elif data.startswith("http"):
                            self._session_url = data
                            break

        if not self._session_url:
            # Some servers don't send an explicit session URL — use base
            self._session_url = f"{base}/messages"

        logger.info("[MCP %s] SSE session: %s", self.config.id, self._session_url)

        # Initialize
        await self._send_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "multi-agent-llm", "version": "5.0"},
        })
        await self._send_notification("notifications/initialized")

        # Discover tools
        result = await self._send_rpc("tools/list", {})
        self._tools = [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in result.get("tools", [])
        ]
        self._connected = True
        logger.info("[MCP %s] connected — %d tool(s): %s",
                    self.config.id, len(self._tools), [t.name for t in self._tools])
        return True

    async def _connect_http(self) -> bool:
        """Streamable HTTP transport: single POST endpoint."""
        self._session_url = self.config.url.rstrip("/")

        result = await self._send_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "multi-agent-llm", "version": "5.0"},
        })
        await self._send_notification("notifications/initialized")

        result = await self._send_rpc("tools/list", {})
        self._tools = [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in result.get("tools", [])
        ]
        self._connected = True
        logger.info("[MCP %s] connected (HTTP) — %d tool(s): %s",
                    self.config.id, len(self._tools), [t.name for t in self._tools])
        return True

    # ── JSON-RPC helpers ───────────────────────────────────────────────────

    async def _send_rpc(self, method: str, params: dict) -> dict:
        msg = {"jsonrpc": "2.0", "id": self._next_id(), "method": method, "params": params}
        async with httpx.AsyncClient(timeout=_CALL_TIMEOUT) as client:
            resp = await client.post(
                self._session_url or self.config.url,
                json=msg,
                headers=self._build_headers(),
            )
            resp.raise_for_status()
            if resp.status_code == 202 or not resp.content:
                return {}
            # Response might be SSE stream or plain JSON
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return self._parse_sse_response(resp.text)
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error']}")
            return data.get("result", data)

    async def _send_notification(self, method: str) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": {}}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    self._session_url or self.config.url,
                    json=msg, headers=self._build_headers(),
                )
        except Exception:
            pass  # Notifications are fire-and-forget

    def _parse_sse_response(self, text: str) -> dict:
        """Extract JSON-RPC result from an SSE-format response body."""
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    if "result" in data:
                        return data["result"]
                    if "error" in data:
                        raise RuntimeError(f"MCP error: {data['error']}")
                except json.JSONDecodeError:
                    continue
        return {}

    # ── Tool execution ─────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool on this MCP server. Reconnects if needed."""
        if not self._connected:
            ok = await self.connect()
            if not ok:
                return f"[MCP {self.config.id}: not connected]"

        try:
            result = await self._send_rpc("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            return self._extract_content(result)
        except Exception as exc:
            logger.error("[MCP %s] tool call '%s' failed: %s", self.config.id, tool_name, exc)
            # Try reconnecting once
            self._connected = False
            self._session_url = None
            ok = await self.connect()
            if ok:
                try:
                    result = await self._send_rpc("tools/call", {"name": tool_name, "arguments": arguments})
                    return self._extract_content(result)
                except Exception as exc2:
                    return f"[MCP tool error: {exc2}]"
            return f"[MCP {self.config.id}: reconnect failed]"

    def _extract_content(self, result: dict) -> str:
        """Pull text/content from a tools/call response."""
        if not result:
            return "[empty result]"
        # Standard MCP result format: { content: [{type: "text", text: "..."}] }
        content = result.get("content", result)
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif item.get("type") == "image":
                        parts.append(f"[image: {item.get('url', '')}]")
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        if isinstance(content, str):
            return content
        return json.dumps(content, indent=2)

    async def disconnect(self):
        self._connected = False
        self._session_url = None
        self._tools = []
