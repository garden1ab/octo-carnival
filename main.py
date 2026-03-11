"""
main.py — Application entrypoint v4.

New in v4
---------
  • GET  /settings                → Return current controller + prompt settings
  • PUT  /settings/controller     → Update controller LLM (provider/model/key/etc.)
  • PUT  /settings/prompts        → Update all system prompts
  • POST /settings/prompts/reset  → Reset prompts to built-in defaults
  • /health/stream now also broadcasts current controller info
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

from agent_registry import AgentDefinition, AgentRegistry
from api_integrations.registry import IntegrationRegistry, UserIntegration
from chat_handler import ChatHandler, ChatRequest, ChatResponse
from config import load_config
from controller import MainController
from document_handler import DocumentHandler
from schemas import DocumentChunk, OrchestratorRequest, OrchestratorResponse
from system_settings import ControllerSettings, PromptSettings, SystemSettings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Global singletons ─────────────────────────────────────────────────────────
_config = load_config()
logging.getLogger().setLevel(_config.log_level)

_agent_registry    = AgentRegistry()
_integration_registry = IntegrationRegistry()
_system_settings: Optional[SystemSettings]  = None
_controller:      Optional[MainController]  = None
_doc_handler:     Optional[DocumentHandler] = None
_chat_handler:    Optional[ChatHandler]     = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _system_settings, _controller, _doc_handler, _chat_handler

    logger.info("Booting Multi-Agent LLM Orchestration System v4…")

    _system_settings = SystemSettings(_config.controller)
    _agent_registry.seed_from_config(_config.agents)

    _doc_handler = DocumentHandler(
        chunk_size=_config.chunk_size,
        chunk_overlap=_config.chunk_overlap,
        upload_dir=_config.upload_dir,
    )
    _controller = MainController(_config, _agent_registry, _integration_registry, _system_settings)
    _chat_handler = ChatHandler(_agent_registry)

    logger.info("Ready — %d agent(s): %s", len(_agent_registry.agents), list(_agent_registry.agents.keys()))
    yield
    logger.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Multi-Agent LLM Orchestration API", version="4.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Serve React build ─────────────────────────────────────────────────────────
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


# ── Health + SSE ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    ctrl = _system_settings.controller if _system_settings else None
    return {
        "status": "ok",
        "controller": {"provider": ctrl.provider, "model": ctrl.model} if ctrl else {},
        "agents": [{"id": aid, "provider": w.config.provider, "model": w.config.model}
                   for aid, w in _agent_registry.agents.items()],
        "integrations": len(_integration_registry.list()),
    }


@app.get("/health/stream")
async def health_stream():
    async def _gen():
        while True:
            ctrl = _system_settings.controller if _system_settings else None
            payload = {
                "controller": {"provider": ctrl.provider, "model": ctrl.model} if ctrl else {},
                "agents": [{"id": aid, "provider": w.config.provider, "model": w.config.model}
                           for aid, w in _agent_registry.agents.items()],
                "integrations": len(_integration_registry.list()),
                "status": "ok",
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── System Settings ───────────────────────────────────────────────────────────

@app.get("/settings")
async def get_settings():
    if not _system_settings:
        raise HTTPException(status_code=503, detail="Settings not initialised")
    return _system_settings.to_response()


@app.put("/settings/controller")
async def update_controller(update: ControllerSettings):
    if not _system_settings:
        raise HTTPException(status_code=503, detail="Settings not initialised")
    result = _system_settings.update_controller(update)
    safe = result.model_copy()
    if safe.api_key:
        safe.api_key = "***"
    return safe


@app.put("/settings/prompts")
async def update_prompts(update: PromptSettings):
    if not _system_settings:
        raise HTTPException(status_code=503, detail="Settings not initialised")
    return _system_settings.update_prompts(update)


@app.post("/settings/prompts/reset")
async def reset_prompts():
    if not _system_settings:
        raise HTTPException(status_code=503, detail="Settings not initialised")
    return _system_settings.reset_prompts()


# ── Agent CRUD ────────────────────────────────────────────────────────────────
@app.get("/agents")
async def list_agents():
    return _agent_registry.list_definitions()

@app.post("/agents", status_code=201)
async def create_agent(defn: AgentDefinition):
    if defn.agent_id in _agent_registry.agents:
        raise HTTPException(status_code=409, detail=f"Agent '{defn.agent_id}' already exists. Use PUT to update.")
    try:
        return _agent_registry.add_or_update(defn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, defn: AgentDefinition):
    defn.agent_id = agent_id
    try:
        return _agent_registry.add_or_update(defn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not _agent_registry.remove(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": agent_id}


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not _chat_handler:
        raise HTTPException(status_code=503, detail="Chat handler not ready")
    try:
        return await _chat_handler.chat(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Chat error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


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
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": iid}

@app.patch("/integrations/{iid}/toggle")
async def toggle_integration(iid: str, enabled: bool):
    integ = _integration_registry.get(iid)
    if not integ:
        raise HTTPException(status_code=404, detail="Not found")
    integ.enabled = enabled
    return integ


# ── Orchestration ─────────────────────────────────────────────────────────────
@app.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest):
    if not _controller:
        raise HTTPException(status_code=503, detail="Controller not initialised")
    if not _agent_registry.agents:
        raise HTTPException(status_code=400, detail="No agents configured.")
    try:
        return await _controller.run(request)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/orchestrate/with-files", response_model=OrchestratorResponse)
async def orchestrate_with_files(
    prompt: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
):
    if not _controller or not _doc_handler:
        raise HTTPException(status_code=503, detail="System not initialised")
    if not _agent_registry.agents:
        raise HTTPException(status_code=400, detail="No agents configured.")

    chunks: list[DocumentChunk] = []
    for upload in files:
        try:
            data = await upload.read()
            chunks.extend(_doc_handler.process(upload.filename or "upload", data))
        except Exception as exc:
            logger.error("Failed to process '%s': %s", upload.filename, exc)

    req = OrchestratorRequest(prompt=prompt, **({"session_id": session_id} if session_id else {}))
    try:
        return await _controller.run(req, document_chunks=chunks)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host=_config.host, port=_config.port,
                log_level=_config.log_level.lower(), reload=False)
