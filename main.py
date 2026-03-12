"""
main.py — Application entrypoint v6.

New in v6
---------
  MCP server management:
  GET  /mcp                   → List all MCP servers + connection status
  POST /mcp                   → Add + connect a new MCP server
  DELETE /mcp/{id}            → Remove server
  POST /mcp/{id}/connect      → (Re)connect a server
  POST /mcp/{id}/disconnect   → Disconnect a server
  PATCH /mcp/{id}/toggle      → Enable / disable
  GET  /mcp/{id}/tools        → List tools from one server

  MCP servers are auto-loaded from MCP_N_* env vars at startup and
  connected in parallel alongside the rest of boot.

  /debug/tool-test now shows both HTTP and MCP tools available.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_registry import AgentDefinition, AgentRegistry
from api_integrations.docdb import DocDBRegistry, DocumentDatabase
from api_integrations.registry import IntegrationRegistry, UserIntegration
from api_integrations.tool_executor import ToolExecutor
from chat_handler import ChatHandler, ChatRequest, ChatResponse
from config import load_config
from controller import MainController
from document_handler import DocumentHandler
from mcp.client import MCPServerConfig
from mcp.registry import MCPRegistry, load_mcp_servers_from_env
from schemas import DocumentChunk, OrchestratorRequest, OrchestratorResponse
from system_settings import ControllerSettings, PromptSettings, SystemSettings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────
_config = load_config()
logging.getLogger().setLevel(_config.log_level)

_agent_registry       = AgentRegistry()
_integration_registry = IntegrationRegistry()
_mcp_registry         = MCPRegistry()
_docdb_registry       = DocDBRegistry()
_system_settings: Optional[SystemSettings]  = None
_controller:      Optional[MainController]  = None
_doc_handler:     Optional[DocumentHandler] = None
_chat_handler:    Optional[ChatHandler]     = None


def _make_executor() -> ToolExecutor:
    return ToolExecutor(_integration_registry, _mcp_registry, _docdb_registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _system_settings, _controller, _doc_handler, _chat_handler

    logger.info("Booting Multi-Agent LLM Orchestration System v6…")

    _system_settings = SystemSettings(_config.controller)
    _agent_registry.seed_from_config(_config.agents)

    _doc_handler = DocumentHandler(
        chunk_size=_config.chunk_size,
        chunk_overlap=_config.chunk_overlap,
        upload_dir=_config.upload_dir,
    )
    _controller = MainController(
        _config, _agent_registry, _integration_registry,
        _system_settings, _mcp_registry, _docdb_registry,
    )
    _chat_handler = ChatHandler(_agent_registry)

    # ── Boot MCP servers from env ──────────────────────────────────────────
    mcp_configs = load_mcp_servers_from_env()
    for cfg in mcp_configs:
        _mcp_registry.add_server(cfg)

    if mcp_configs:
        logger.info("Connecting %d MCP server(s)…", len(mcp_configs))
        await _mcp_registry.connect_all()
        for srv in _mcp_registry.list_servers():
            status = "✓" if srv["connected"] else "✗"
            logger.info("  %s %s — %d tool(s)", status, srv["id"], srv["tool_count"])

    logger.info("Ready — %d agent(s): %s", len(_agent_registry.agents),
                list(_agent_registry.agents.keys()))
    yield
    await _mcp_registry.disconnect_all()
    logger.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Multi-Agent LLM Orchestration API", version="6.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Static ────────────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"
if STATIC_DIR.exists():
    assets = STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/ui/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        fp = STATIC_DIR / full_path
        return FileResponse(str(fp) if fp.exists() else str(STATIC_DIR / "index.html"))


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    ctrl = _system_settings.controller if _system_settings else None
    return {
        "status": "ok",
        "controller": {"provider": ctrl.provider, "model": ctrl.model} if ctrl else {},
        "agents": [{"id": aid, "provider": w.config.provider, "model": w.config.model}
                   for aid, w in _agent_registry.agents.items()],
        "integrations": len(_integration_registry.list()),
        "mcp_servers": len([s for s in _mcp_registry.list_servers() if s["connected"]]),
    }


@app.get("/health/stream")
async def health_stream():
    async def _gen():
        while True:
            ctrl = _system_settings.controller if _system_settings else None
            mcp_tools_total = sum(
                s["tool_count"] for s in _mcp_registry.list_servers() if s["connected"]
            )
            payload = {
                "controller": {"provider": ctrl.provider, "model": ctrl.model} if ctrl else {},
                "agents": [{"id": aid, "provider": w.config.provider, "model": w.config.model}
                           for aid, w in _agent_registry.agents.items()],
                "integrations": len(_integration_registry.list()),
                "mcp_servers": len([s for s in _mcp_registry.list_servers() if s["connected"]]),
                "mcp_tools": mcp_tools_total,
                "status": "ok",
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Settings ──────────────────────────────────────────────────────────────────
@app.get("/settings")
async def get_settings():
    if not _system_settings:
        raise HTTPException(503, "Not initialised")
    return _system_settings.to_response()

@app.put("/settings/controller")
async def update_controller(update: ControllerSettings):
    if not _system_settings:
        raise HTTPException(503, "Not initialised")
    result = _system_settings.update_controller(update)
    safe = result.model_copy()
    if safe.api_key:
        safe.api_key = "***"
    return safe

@app.put("/settings/prompts")
async def update_prompts(update: PromptSettings):
    if not _system_settings:
        raise HTTPException(503, "Not initialised")
    return _system_settings.update_prompts(update)

@app.post("/settings/prompts/reset")
async def reset_prompts():
    if not _system_settings:
        raise HTTPException(503, "Not initialised")
    return _system_settings.reset_prompts()


# ── MCP Server CRUD ───────────────────────────────────────────────────────────

class MCPServerRequest(BaseModel):
    id: str
    name: str
    url: str
    transport: str = "sse"
    api_key: Optional[str] = None
    description: str = ""
    enabled: bool = True
    auto_connect: bool = True


@app.get("/mcp")
async def list_mcp_servers():
    return _mcp_registry.list_servers()


@app.post("/mcp", status_code=201)
async def add_mcp_server(req: MCPServerRequest):
    if _mcp_registry.get_server(req.id):
        raise HTTPException(409, f"MCP server '{req.id}' already exists")

    cfg = MCPServerConfig(
        id=req.id, name=req.name, url=req.url,
        transport=req.transport, api_key=req.api_key,
        enabled=req.enabled, description=req.description,
    )
    _mcp_registry.add_server(cfg)

    if req.auto_connect and req.enabled:
        connected = await _mcp_registry.connect_server(req.id)
        if not connected:
            logger.warning("MCP server '%s' added but could not connect", req.id)

    return _mcp_registry.list_servers()


@app.delete("/mcp/{server_id}")
async def remove_mcp_server(server_id: str):
    client = _mcp_registry.get_server(server_id)
    if not client:
        raise HTTPException(404, "MCP server not found")
    await client.disconnect()
    _mcp_registry.remove_server(server_id)
    return {"deleted": server_id}


@app.post("/mcp/{server_id}/connect")
async def connect_mcp_server(server_id: str):
    ok = await _mcp_registry.connect_server(server_id)
    if not ok:
        raise HTTPException(500, f"Failed to connect to MCP server '{server_id}'")
    srv = next((s for s in _mcp_registry.list_servers() if s["id"] == server_id), None)
    return srv


@app.post("/mcp/{server_id}/disconnect")
async def disconnect_mcp_server(server_id: str):
    client = _mcp_registry.get_server(server_id)
    if not client:
        raise HTTPException(404, "Not found")
    await client.disconnect()
    return {"disconnected": server_id}


@app.patch("/mcp/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, enabled: bool):
    client = _mcp_registry.get_server(server_id)
    if not client:
        raise HTTPException(404, "Not found")
    client.config.enabled = enabled
    if enabled and not client.is_connected:
        await _mcp_registry.connect_server(server_id)
    return next((s for s in _mcp_registry.list_servers() if s["id"] == server_id), None)


@app.get("/mcp/{server_id}/tools")
async def get_mcp_tools(server_id: str):
    client = _mcp_registry.get_server(server_id)
    if not client:
        raise HTTPException(404, "Not found")
    return {"server_id": server_id, "connected": client.is_connected,
            "tools": [{"name": t.name, "description": t.description,
                       "input_schema": t.input_schema} for t in client.tools]}


# ── Document Database CRUD ───────────────────────────────────────────────────

@app.get("/docdb")
async def list_docdb():
    """List all registered document databases."""
    return [
        {
            "id": db.id, "name": db.name, "description": db.description,
            "base_url": db.base_url, "enabled": db.enabled,
            "tools": [t["name"] for t in db.to_tool_definitions()],
            "list_path": db.list_path, "get_path": db.get_path,
            "search_path": db.search_path,
            "id_field": db.id_field, "title_field": db.title_field,
            "content_field": db.content_field,
        }
        for db in _docdb_registry.list()
    ]


@app.post("/docdb", status_code=201)
async def add_docdb(db: DocumentDatabase):
    if _docdb_registry.get(db.id):
        raise HTTPException(409, f"Document database '{db.id}' already exists")
    _docdb_registry.add(db)
    return {"registered": db.id, "tools": [t["name"] for t in db.to_tool_definitions()]}


@app.put("/docdb/{db_id}")
async def update_docdb(db_id: str, db: DocumentDatabase):
    db.id = db_id
    _docdb_registry.add(db)
    return {"updated": db_id, "tools": [t["name"] for t in db.to_tool_definitions()]}


@app.delete("/docdb/{db_id}")
async def delete_docdb(db_id: str):
    if not _docdb_registry.remove(db_id):
        raise HTTPException(404, "Document database not found")
    return {"deleted": db_id}


@app.patch("/docdb/{db_id}/toggle")
async def toggle_docdb(db_id: str, enabled: bool):
    db = _docdb_registry.get(db_id)
    if not db:
        raise HTTPException(404, "Not found")
    db.enabled = enabled
    return {"id": db_id, "enabled": enabled}


@app.post("/docdb/{db_id}/test-list")
async def test_docdb_list(db_id: str, body: dict = {}):
    """Quick test: call the list endpoint and return normalised output."""
    db = _docdb_registry.get(db_id)
    if not db:
        raise HTTPException(404, "Not found")
    from api_integrations.docdb_executor import DocDBExecutor
    result = await DocDBExecutor(db).execute("list", body)
    return {"result": result}


@app.post("/docdb/{db_id}/test-get")
async def test_docdb_get(db_id: str, body: dict):
    """Quick test: call the get endpoint with a document ID."""
    db = _docdb_registry.get(db_id)
    if not db:
        raise HTTPException(404, "Not found")
    if "id" not in body:
        raise HTTPException(400, "Body must include 'id'")
    from api_integrations.docdb_executor import DocDBExecutor
    result = await DocDBExecutor(db).execute("get", body)
    return {"result": result}


# ── Agent CRUD ────────────────────────────────────────────────────────────────
@app.get("/agents")
async def list_agents():
    return _agent_registry.list_definitions()

@app.post("/agents", status_code=201)
async def create_agent(defn: AgentDefinition):
    if defn.agent_id in _agent_registry.agents:
        raise HTTPException(409, f"Agent '{defn.agent_id}' already exists")
    try:
        return _agent_registry.add_or_update(defn)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, defn: AgentDefinition):
    defn.agent_id = agent_id
    try:
        return _agent_registry.add_or_update(defn)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not _agent_registry.remove(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"deleted": agent_id}


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not _chat_handler:
        raise HTTPException(503, "Chat handler not ready")
    try:
        return await _chat_handler.chat(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        raise HTTPException(500, str(exc))


# ── Integrations ──────────────────────────────────────────────────────────────
@app.get("/integrations")
async def list_integrations():
    return _integration_registry.list()

@app.post("/integrations")
async def add_integration(i: UserIntegration):
    return _integration_registry.add(i)

@app.delete("/integrations/{iid}")
async def remove_integration(iid: str):
    if not _integration_registry.remove(iid):
        raise HTTPException(404, "Not found")
    return {"deleted": iid}

@app.patch("/integrations/{iid}/toggle")
async def toggle_integration(iid: str, enabled: bool):
    integ = _integration_registry.get(iid)
    if not integ:
        raise HTTPException(404, "Not found")
    integ.enabled = enabled
    return integ


# ── Debug: tool test ──────────────────────────────────────────────────────────
@app.post("/debug/tool-test")
async def debug_tool_test(body: dict):
    from tool_loop import run_with_tools
    from api_clients.base import LLMMessage

    agent_id = body.get("agent_id")
    prompt = body.get("prompt", "What is the current weather in London?")

    worker = (_agent_registry.agents.get(agent_id)
              if agent_id else next(iter(_agent_registry.agents.values()), None))
    if not worker:
        raise HTTPException(400, "No agent found")

    executor = _make_executor()
    http_tools = _integration_registry.to_tool_definitions()
    mcp_tools  = _mcp_registry.to_tool_definitions()
    all_tools  = http_tools + mcp_tools

    if not all_tools:
        raise HTTPException(400, "No enabled tools — add integrations or MCP servers first")

    messages = [
        LLMMessage(role="system", content=(
            "You are a helpful assistant with access to external tools. "
            "Use them to answer questions requiring live data."
        )),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        answer, trace = await run_with_tools(worker.client, messages, executor, all_tools, max_iterations=3)
        return {
            "agent": worker.agent_id,
            "provider": worker.config.provider,
            "model": worker.config.model,
            "http_tools": [t["name"] for t in http_tools],
            "mcp_tools": [t["name"] for t in mcp_tools],
            "tool_calls_made": len(trace),
            "tool_trace": trace,
            "answer": answer,
        }
    except Exception as exc:
        logger.exception("Tool test failed: %s", exc)
        raise HTTPException(500, str(exc))


# ── Orchestration ─────────────────────────────────────────────────────────────
@app.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    if not _controller:
        raise HTTPException(503, "Controller not initialised")
    if not _agent_registry.agents:
        raise HTTPException(400, "No agents configured")
    try:
        return await _controller.run(request)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(500, str(exc))

@app.post("/orchestrate/with-files", response_model=OrchestratorResponse)
async def orchestrate_with_files(
    prompt: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    if not _controller or not _doc_handler:
        raise HTTPException(503, "System not initialised")
    if not _agent_registry.agents:
        raise HTTPException(400, "No agents configured")

    chunks: list[DocumentChunk] = []
    for upload in files:
        try:
            data = await upload.read()
            chunks.extend(_doc_handler.process(upload.filename or "upload", data))
        except Exception as exc:
            logger.error("File processing failed: %s", exc)

    req = OrchestratorRequest(prompt=prompt, **({"session_id": session_id} if session_id else {}))
    try:
        return await _controller.run(req, document_chunks=chunks)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(500, str(exc))


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host=_config.host, port=_config.port,
                log_level=_config.log_level.lower(), reload=False)
