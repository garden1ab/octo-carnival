"""
api_integrations/docdb_executor.py — Executes document database tool calls.

Handles list, get, and search operations, normalising API responses
into clean labelled output the LLM can actually use.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from api_integrations.docdb import DocumentDatabase

logger = logging.getLogger(__name__)

_TIMEOUT = 20


class DocDBExecutor:
    """Executes list/get/search operations against a DocumentDatabase."""

    def __init__(self, db: DocumentDatabase):
        self.db = db

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        h.update(self.db.extra_headers)
        auth = self.db.auth
        if auth and auth.api_key:
            if auth.type == "bearer":
                h["Authorization"] = f"Bearer {auth.api_key}"
            elif auth.type == "api_key":
                h[auth.header_name] = f"{auth.prefix} {auth.api_key}".strip()
            elif auth.type == "basic":
                import base64
                h["Authorization"] = "Basic " + base64.b64encode(auth.api_key.encode()).decode()
        return h

    async def execute(self, operation: str, params: dict[str, Any]) -> str:
        try:
            if operation == "list":
                return await self._list(params)
            elif operation == "get":
                return await self._get(params)
            elif operation == "search":
                return await self._search(params)
            else:
                return f"[Unknown operation: {operation}]"
        except httpx.HTTPStatusError as exc:
            return f"[DocDB error {exc.response.status_code}: {exc.response.text[:200]}]"
        except Exception as exc:
            logger.error("DocDB '%s' %s failed: %s", self.db.id, operation, exc)
            return f"[DocDB error: {exc}]"

    async def _list(self, params: dict[str, Any]) -> str:
        db = self.db
        url = db.base_url.rstrip("/") + db.list_path

        query_params: dict[str, Any] = {db.page_size_param: db.page_size}
        body: Optional[dict] = None

        if db.list_method.upper() == "GET":
            query = params.get("query", "")
            if query and db.list_search_param:
                query_params[db.list_search_param] = query
        else:
            body = self._render_body(db.list_body_template, params) if db.list_body_template else params

        data = await self._request(db.list_method, url, query_params=query_params, body=body)
        return self._format_list_response(data)

    async def _get(self, params: dict[str, Any]) -> str:
        db = self.db
        doc_id = str(params.get("id", ""))
        path = db.get_path.replace("{id}", doc_id)
        url = db.base_url.rstrip("/") + path

        body: Optional[dict] = None
        if db.get_method.upper() != "GET":
            body = self._render_body(db.get_body_template, params) if db.get_body_template else params

        data = await self._request(db.get_method, url, body=body)
        return self._format_document(data)

    async def _search(self, params: dict[str, Any]) -> str:
        db = self.db
        if not db.search_path:
            return await self._list(params)  # fall back to list+filter

        url = db.base_url.rstrip("/") + db.search_path
        query = params.get("query", "")

        body: Optional[dict] = None
        query_params: dict[str, Any] = {}

        if db.search_method.upper() == "GET":
            if db.list_search_param:
                query_params[db.list_search_param] = query
        else:
            body = self._render_body(db.search_body_template, params) if db.search_body_template else params

        data = await self._request(db.search_method, url, query_params=query_params, body=body)
        return self._format_list_response(data)

    async def _request(
        self,
        method: str,
        url: str,
        query_params: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(
                method.upper(), url,
                headers=self._headers(),
                params=query_params or {},
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    def _format_list_response(self, data: Any) -> str:
        """Format a list/search response into a clean document index."""
        db = self.db
        # Navigate to the results array
        items = data
        if db.list_results_key and isinstance(data, dict):
            items = data.get(db.list_results_key, data)
        if not isinstance(items, list):
            # Try common envelope keys
            for key in ("results", "items", "documents", "data", "hits", "records"):
                if isinstance(data, dict) and key in data:
                    items = data[key]
                    break
            else:
                items = [data] if isinstance(data, dict) else []

        if not items:
            return f"[{db.name}] No documents found."

        lines = [f"[{db.name}] Found {len(items)} document(s):\n"]
        for item in items[:db.page_size]:
            doc_id = self._field(item, db.id_field, "?")
            title  = self._field(item, db.title_field, "(untitled)")
            summary = self._field(item, db.summary_field, "") if db.summary_field else ""

            line = f"  • ID: {doc_id} | Title: {title}"
            if summary:
                line += f"\n    Summary: {str(summary)[:200]}"
            lines.append(line)

        lines.append(f"\nUse {db.id}_get with the ID to fetch full document content.")
        return "\n".join(lines)

    def _format_document(self, data: Any) -> str:
        """Format a single document fetch into labelled content."""
        db = self.db
        if not isinstance(data, dict):
            return str(data)[:8000]

        doc_id  = self._field(data, db.id_field, "?")
        title   = self._field(data, db.title_field, "(untitled)")
        content = self._field(data, db.content_field, "")

        # If content is a dict/list (rich text, blocks, etc.) stringify it
        if isinstance(content, (dict, list)):
            content = json.dumps(content, indent=2)

        if not content:
            # Fall back: concatenate all string values
            content = "\n".join(
                f"{k}: {v}" for k, v in data.items()
                if isinstance(v, str) and k not in (db.id_field, db.title_field)
            )

        result = f"[{db.name}] Document: {title} (ID: {doc_id})\n\n{content}"
        # Truncate to keep context window manageable
        if len(result) > 12000:
            result = result[:12000] + "\n\n[... document truncated at 12000 chars ...]"
        return result

    @staticmethod
    def _field(item: dict, field_name: str, default: Any = "") -> Any:
        """Get a field value, supporting dot-notation for nested fields."""
        if not field_name:
            return default
        parts = field_name.split(".")
        val = item
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, default)
            else:
                return default
        return val if val is not None else default

    @staticmethod
    def _render_body(template: str, params: dict) -> dict:
        """Substitute {param} placeholders in a JSON body template string."""
        rendered = template
        for k, v in params.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            return params
