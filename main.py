"""
main.py — Application entrypoint.

Exposes a FastAPI REST server with two endpoints:

  POST /orchestrate
      Body: { "prompt": "...", "session_id": "..." }
      Returns: OrchestratorResponse (JSON)

  POST /orchestrate/with-files
      Form fields: prompt (str), session_id (str, optional)
      File fields:  files[] (multipart, zero or more)
      Returns: OrchestratorResponse (JSON)

Run directly:
    python main.py

Or via uvicorn:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import load_config
from controller import MainController
from document_handler import DocumentHandler
from schemas import (
    DocumentChunk,
    OrchestratorRequest,
    OrchestratorResponse,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

_config = load_config()
logging.getLogger().setLevel(_config.log_level)

_controller: Optional[MainController] = None
_doc_handler: Optional[DocumentHandler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared singletons on startup."""
    global _controller, _doc_handler
    logger.info("Starting Multi-Agent LLM Orchestration System…")
    _doc_handler = DocumentHandler(
        chunk_size=_config.chunk_size,
        chunk_overlap=_config.chunk_overlap,
        upload_dir=_config.upload_dir,
    )
    _controller = MainController(_config)
    logger.info(
        "Ready — %d worker agent(s) configured: %s",
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
    description=(
        "Send a prompt (and optional documents) to a controller LLM that "
        "decomposes the task, dispatches sub-tasks to worker agents, and "
        "returns a consolidated final answer."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Simple liveness probe."""
    return {"status": "ok", "agents": [a.agent_id for a in _config.agents]}


@app.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(request: OrchestratorRequest) -> OrchestratorResponse:
    """
    Run the full orchestration pipeline for a plain text prompt.
    No file uploads — use /orchestrate/with-files for that.
    """
    if _controller is None:
        raise HTTPException(status_code=503, detail="Controller not initialised")

    try:
        return await _controller.run(request)
    except Exception as exc:
        logger.exception("Orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/orchestrate/with-files", response_model=OrchestratorResponse)
async def orchestrate_with_files(
    prompt: str = Form(..., description="The user's prompt"),
    session_id: Optional[str] = Form(None, description="Optional session ID"),
    files: list[UploadFile] = File(default=[], description="Optional document uploads"),
) -> OrchestratorResponse:
    """
    Run the orchestration pipeline with optional file uploads.

    Files are parsed, chunked, and forwarded to the appropriate worker agents
    as decided by the Controller LLM.
    """
    if _controller is None or _doc_handler is None:
        raise HTTPException(status_code=503, detail="System not initialised")

    # --- Parse uploaded files ---
    all_chunks: list[DocumentChunk] = []
    for upload in files:
        try:
            data = await upload.read()
            chunks = _doc_handler.process(upload.filename or "upload", data)
            all_chunks.extend(chunks)
            logger.info(
                "Processed upload '%s' → %d chunk(s)", upload.filename, len(chunks)
            )
        except Exception as exc:
            logger.error("Failed to process '%s': %s", upload.filename, exc)
            # Non-fatal: continue with remaining files

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
# CLI entrypoint (also starts the server)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=_config.host,
        port=_config.port,
        log_level=_config.log_level.lower(),
        reload=False,
    )
