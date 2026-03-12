"""
api_integrations/docdb.py — Document Database integration.

A DocumentDatabase registers multiple coordinated tools from a single config:

  {db_id}_list    — list/search documents → returns id, title, metadata
  {db_id}_get     — fetch full document by id
  {db_id}_search  — (optional) full-text/semantic search endpoint

The agent uses them in sequence:
  1. Call _list (or _search) to discover what documents exist
  2. Read titles/descriptions to decide which are relevant
  3. Call _get for each document of interest
  4. Synthesise the content

Supports common document database APIs:
  - REST with GET /documents + GET /documents/{id}
  - Custom path templates for each operation
  - Optional search endpoint
  - Response field mapping (id_field, title_field, content_field)
    so the agent gets clean labelled output regardless of API shape
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocDBAuth(BaseModel):
    type: str = "bearer"          # bearer | api_key | basic | none
    api_key: Optional[str] = None
    header_name: str = "Authorization"
    prefix: str = "Bearer"


class DocumentDatabase(BaseModel):
    """Configuration for a document database API integration."""

    id: str                       # e.g. "confluence", "notion-wiki"
    name: str                     # Display name
    description: str              # What kinds of documents live here
    base_url: str                 # e.g. "https://wiki.example.com/api"

    # ── Endpoint templates ──────────────────────────────────────────────────
    # Use {param} placeholders. All are relative to base_url.
    list_path: str = "/documents"
    # Optional query param to filter: appended as ?{search_param}={query}
    list_search_param: Optional[str] = "q"
    # Path to fetch a single document — must contain {id}
    get_path: str = "/documents/{id}"
    # Optional dedicated search endpoint (leave blank to use list + search_param)
    search_path: Optional[str] = None

    # ── Response field mapping ───────────────────────────────────────────────
    # Top-level key that holds the array in a list response (blank = root is array)
    list_results_key: str = ""
    # Field names within each item
    id_field: str = "id"
    title_field: str = "title"
    summary_field: str = ""       # optional brief summary field
    content_field: str = "content"

    # ── Auth ─────────────────────────────────────────────────────────────────
    auth: Optional[DocDBAuth] = None
    extra_headers: dict[str, str] = {}

    # ── Pagination ───────────────────────────────────────────────────────────
    page_size: int = 50           # max items to return in list
    page_size_param: str = "limit"

    enabled: bool = True

    # ── HTTP method overrides ────────────────────────────────────────────────
    list_method: str = "GET"
    get_method: str = "GET"
    search_method: str = "GET"

    # ── POST body template (JSON string, use {param} substitution) ───────────
    # Only used when method is POST. Leave blank for GET.
    list_body_template: str = ""
    get_body_template: str = ""
    search_body_template: str = ""

    def to_tool_definitions(self) -> list[dict]:
        """Return the 2-3 tool definitions this database exposes."""
        tools = []

        # ── list tool ──────────────────────────────────────────────────────
        tools.append({
            "name": f"{self.id}_list",
            "description": (
                f"List available documents in {self.name}. "
                f"{self.description} "
                f"Returns document IDs, titles, and summaries. "
                f"Use this first to discover what documents are available, "
                f"then call {self.id}_get to fetch the ones you need."
                + (f" Pass a query to filter results." if self.list_search_param else "")
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    **({"query": {
                        "type": "string",
                        "description": "Optional search/filter query to narrow results",
                    }} if self.list_search_param else {}),
                },
                "required": [],
            },
        })

        # ── get tool ──────────────────────────────────────────────────────
        tools.append({
            "name": f"{self.id}_get",
            "description": (
                f"Fetch the full content of a specific document from {self.name} by its ID. "
                f"Call {self.id}_list first to get document IDs."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Document ID as returned by the list tool",
                    },
                },
                "required": ["id"],
            },
        })

        # ── search tool (if dedicated endpoint configured) ─────────────────
        if self.search_path:
            tools.append({
                "name": f"{self.id}_search",
                "description": (
                    f"Full-text or semantic search within {self.name}. "
                    f"Returns matching document IDs and snippets. "
                    f"Use when you know what you're looking for; "
                    f"use {self.id}_list to browse all documents."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                    },
                    "required": ["query"],
                },
            })

        return tools


class DocDBRegistry:
    """Registry of document database integrations."""

    def __init__(self):
        self._dbs: dict[str, DocumentDatabase] = {}

    def add(self, db: DocumentDatabase) -> DocumentDatabase:
        self._dbs[db.id] = db
        logger.info("DocDB registered: %s (%s)", db.id, db.base_url)
        return db

    def remove(self, db_id: str) -> bool:
        if db_id in self._dbs:
            del self._dbs[db_id]
            return True
        return False

    def get(self, db_id: str) -> Optional[DocumentDatabase]:
        return self._dbs.get(db_id)

    def list(self) -> list[DocumentDatabase]:
        return list(self._dbs.values())

    def find_for_tool(self, tool_name: str) -> Optional[tuple[DocumentDatabase, str]]:
        """
        Given a tool name like "confluence_list" or "notion_get",
        return (DocumentDatabase, operation) or None.
        """
        for op in ("_list", "_get", "_search"):
            if tool_name.endswith(op):
                db_id = tool_name[: -len(op)]
                db = self._dbs.get(db_id)
                if db:
                    return db, op[1:]  # "list" | "get" | "search"
        return None

    def to_tool_definitions(self) -> list[dict]:
        """All tool definitions from all enabled databases."""
        defs = []
        for db in self._dbs.values():
            if db.enabled:
                defs.extend(db.to_tool_definitions())
        return defs
