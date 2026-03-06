"""
main.py — Application entrypoint with FastAPI REST server + React UI.

Endpoints
---------
  GET  /                          → Serves React UI (index.html)
  GET  /health                    → Liveness probe
  POST /orchestrate               → Plain prompt orchestration
  POST /orchestrate/with-files    → Prompt + file uploads
  GET  /integrations              → List configured API integrations
  POST /integrations              → Add a new integration
  DELETE /integrations/{id}       → Remove an integration
  PATCH /integrations/{id}/toggle → Enable/disable integration
  GET  /agents                    → List configured agents
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api_integrations.registry import IntegrationRegistry, UserIntegration
from config import load_config
from controller import MainController
from document_handler import DocumentHandler
from schemas import (
    DocumentChunk,
    OrchestratorRequest,
    OrchestratorResponse,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------
_config = load_config()
logging.getLogger().setLevel(_config.log_level)

_controller: Optional[MainController] = None
_doc_handler: Optional[DocumentHandler] = None
_integration_registry = IntegrationRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _controller, _doc_handler
    logger.info("Starting Multi-Agent LLM Orchestration System…")
    _doc_handler = DocumentHandler(
        chunk_size=_config.chunk_size,
        chunk_overlap=_config.chunk_overlap,
        upload_dir=_config.upload_dir,
    )
    _controller = MainController(_config, _integration_registry)
    logger.info(
        "Ready — %d agent(s): %s",
        len(_config.agents),
        [a.agent_id for a in _config.agents],
    )
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Multi-Agent LLM Orchestration API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Serve React build if present at frontend/dist
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agents": [
            {"id": a.agent_id, "provider": a.provider, "model": a.model}
            for a in _config.agents
        ],
        "integrations": len(_integration_registry.list()),
    }


# ---------------------------------------------------------------------------
# Agent info
# ---------------------------------------------------------------------------
@app.get("/agents")
async def list_agents():
    return [
        {"id": a.agent_id, "provider": a.provider, "model": a.model}
        for a in _config.agents
    ]


# ---------------------------------------------------------------------------
# Integration management
# ---------------------------------------------------------------------------
@app.get("/integrations")
async def list_integrations():
    return _integration_registry.list()


@app.post("/integrations")
async def add_integration(integration: UserIntegration):
    return _integration_registry.add(integration)


@app.delete("/integrations/{integration_id}")
async def remove_integration(integration_id: str):
    removed = _integration_registry.remove(integration_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"deleted": integration_id}


@app.patch("/integrations/{integration_id}/toggle")
async def toggle_integration(integration_id: str, enabled: bool):
    integ = _integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not found")
    integ.enabled = enabled
    return integ


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
@app.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest) -> OrchestratorResponse:
    if _controller is None:
        raise HTTPException(status_code=503, detail="Controller not initialised")
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
) -> OrchestratorResponse:
    if _controller is None or _doc_handler is None:
        raise HTTPException(status_code=503, detail="System not initialised")

    all_chunks: list[DocumentChunk] = []
    for upload in files:
        try:
            data = await upload.read()
            chunks = _doc_handler.process(upload.filename or "upload", data)
            all_chunks.extend(chunks)
        except Exception as exc:
            logger.error("Failed to process '%s': %s", upload.filename, exc)

    request = OrchestratorRequest(
        prompt=prompt,
        **({"session_id": session_id} if session_id else {}),
    )
    try:
        return await _controller.run(request, document_chunks=all_chunks)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=_config.host,
        port=_config.port,
        log_level=_config.log_level.lower(),
        reload=False,
    )
