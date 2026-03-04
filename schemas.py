"""
schemas.py — Pydantic models for structured inter-agent message passing.

All communication between the Controller and Worker Agents is typed here so
that serialisation/deserialisation is consistent throughout the system.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class AgentRole(str, Enum):
    """Semantic roles the Controller can assign to a Worker Agent."""
    RESEARCHER   = "researcher"
    SUMMARIZER   = "summarizer"
    ANALYST      = "analyst"
    WRITER       = "writer"
    CRITIC       = "critic"
    CODER        = "coder"
    GENERAL      = "general"


# ---------------------------------------------------------------------------
# Document chunk (passed from DocumentHandler → Controller → Agent)
# ---------------------------------------------------------------------------

class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    mime_type: str
    chunk_index: int
    total_chunks: int
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Task assignment  (Controller → Worker Agent)
# ---------------------------------------------------------------------------

class SubTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str                          # target agent
    role: AgentRole = AgentRole.GENERAL
    instruction: str                       # specific prompt for this sub-task
    context: Optional[str] = None          # extra context (e.g. partial results)
    document_chunks: list[DocumentChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Agent response  (Worker Agent → Controller)
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    task_id: str
    agent_id: str
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# User-facing API request / response
# ---------------------------------------------------------------------------

class OrchestratorRequest(BaseModel):
    prompt: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestratorResponse(BaseModel):
    session_id: str
    status: TaskStatus
    final_answer: Optional[str] = None
    sub_task_count: int = 0
    agent_responses: list[AgentResponse] = Field(default_factory=list)
    error: Optional[str] = None
    total_duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
