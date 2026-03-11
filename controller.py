"""
controller.py — Main Controller LLM v4.
Reads prompts and controller config from SystemSettings on every request,
so all changes take effect immediately without a restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from api_clients import LLMMessage, build_client
from api_integrations.registry import IntegrationRegistry
from config import AppConfig
from schemas import (
    AgentResponse, AgentRole, DocumentChunk,
    OrchestratorRequest, OrchestratorResponse, SubTask, TaskStatus,
)

logger = logging.getLogger(__name__)


class MainController:
    def __init__(self, config: AppConfig, agent_registry, integration_registry: Optional[IntegrationRegistry] = None, system_settings=None):
        self.config = config
        self._registry = agent_registry
        self._integration_registry = integration_registry
        self._settings = system_settings          # SystemSettings | None
        self._semaphore = asyncio.Semaphore(config.max_concurrent_agents)
        # Build initial client; rebuilt on each request if settings changed
        self._ctrl_client = build_client(config.controller)
        self._ctrl_client_key = self._client_key(config.controller)
        logger.info("Controller ready: %s / %s", config.controller.provider, config.controller.model)

    @staticmethod
    def _client_key(cfg) -> str:
        return f"{cfg.provider}|{cfg.model}|{cfg.base_url}|{cfg.api_key}"

    def _get_ctrl_client(self):
        """Return controller LLM client, rebuilding if settings have changed."""
        if self._settings is None:
            return self._ctrl_client
        cfg = self._settings.controller_as_config()
        key = self._client_key(cfg)
        if key != self._ctrl_client_key:
            self._ctrl_client = build_client(cfg)
            self._ctrl_client_key = key
            logger.info("Controller client rebuilt → %s / %s", cfg.provider, cfg.model)
        return self._ctrl_client

    @property
    def _agents(self):
        return self._registry.agents

    def _prompts(self):
        if self._settings:
            return self._settings.prompts
        # Fallback: import defaults
        from system_settings import PromptSettings
        return PromptSettings()

    # ── Public entry point ─────────────────────────────────────────────────

    async def run(self, request: OrchestratorRequest, document_chunks: list[DocumentChunk] | None = None) -> OrchestratorResponse:
        t0 = time.monotonic()
        chunks = document_chunks or []
        logger.info("Session %s started", request.session_id)

        sub_tasks = await self._decompose(request.prompt, chunks)
        if not sub_tasks:
            return OrchestratorResponse(session_id=request.session_id, status=TaskStatus.FAILED, error="No sub-tasks generated")

        responses = await self._dispatch(sub_tasks)
        final = await self._synthesise(request.prompt, responses)

        return OrchestratorResponse(
            session_id=request.session_id, status=TaskStatus.COMPLETED,
            final_answer=final, sub_task_count=len(sub_tasks),
            agent_responses=responses, total_duration_seconds=time.monotonic() - t0,
        )

    # ── Step 1: Decompose ──────────────────────────────────────────────────

    async def _decompose(self, prompt: str, chunks: list[DocumentChunk]) -> list[SubTask]:
        agents = self._agents
        if not agents:
            return []
        p = self._prompts()
        desc = "\n".join(f"  {aid}: {w.config.provider}/{w.config.model}" for aid, w in agents.items())
        doc_summary = f"{len(chunks)} chunk(s)" if chunks else "none"
        tools_ctx = self._integration_registry.to_prompt_context() if self._integration_registry else ""

        decompose_sys = p.decompose_system.format(agent_descriptions=desc, tools_context=tools_ctx)

        msgs = [
            LLMMessage(role="system", content=decompose_sys),
            LLMMessage(role="user", content=f"User request: {prompt}\nDocuments: {doc_summary}\nDecompose now."),
        ]
        try:
            resp = await self._get_ctrl_client().complete(msgs)
            raw = resp.content.strip()
            # Strip markdown fences if present
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            task_defs = json.loads(raw.strip())
        except Exception as exc:
            logger.error("Decompose failed: %s — fallback to single task", exc)
            task_defs = [{"agent_id": next(iter(agents)), "role": "general", "instruction": prompt, "needs_docs": bool(chunks)}]

        result = []
        for td in task_defs:
            aid = td.get("agent_id", next(iter(agents)))
            if aid not in agents:
                aid = next(iter(agents))
            result.append(SubTask(
                agent_id=aid,
                role=AgentRole(td.get("role", "general")),
                instruction=td["instruction"],
                document_chunks=chunks if td.get("needs_docs") else [],
            ))
        return result

    # ── Step 2: Dispatch ───────────────────────────────────────────────────

    async def _dispatch(self, tasks: list[SubTask]) -> list[AgentResponse]:
        p = self._prompts()
        tools_ctx = self._integration_registry.to_prompt_context() if self._integration_registry else ""

        async def _run(task):
            async with self._semaphore:
                worker = self._agents.get(task.agent_id)
                if not worker:
                    return AgentResponse(task_id=task.task_id, agent_id=task.agent_id,
                                        status=TaskStatus.FAILED, error="Agent not found")
                return await worker.execute(task, tools_context=tools_ctx,
                                            global_system=p.global_agent_system,
                                            role_prompts=p.role_prompts)
        return list(await asyncio.gather(*[_run(t) for t in tasks]))

    # ── Step 3: Synthesise ─────────────────────────────────────────────────

    async def _synthesise(self, prompt: str, responses: list[AgentResponse]) -> str:
        p = self._prompts()
        results = "\n\n".join(
            f"--- {r.agent_id} ({r.status}) ---\n{r.result or '[ERROR: ' + str(r.error) + ']'}"
            for r in responses
        )
        msgs = [
            LLMMessage(role="system", content=p.synthesis_system),
            LLMMessage(role="user", content=f"Original request:\n{prompt}\n\nAgent results:\n{results}\n\nWrite the final response."),
        ]
        try:
            return (await self._get_ctrl_client().complete(msgs)).content
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            return "## Results\n\n" + results
