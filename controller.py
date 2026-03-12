"""
controller.py — Main Controller LLM v5.

Tool execution flow:
  decompose  → plain completion (just needs to output JSON, no tool calls)
  dispatch   → each worker agent runs the tool loop (fetches real API data)
  synthesise → plain completion on the collected results
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from api_clients import LLMMessage, build_client
from api_integrations.registry import IntegrationRegistry
from api_integrations.tool_executor import ToolExecutor
from config import AppConfig
from schemas import (
    AgentResponse, AgentRole, DocumentChunk,
    OrchestratorRequest, OrchestratorResponse, SubTask, TaskStatus,
)

logger = logging.getLogger(__name__)


class MainController:
    def __init__(self, config: AppConfig, agent_registry,
                 integration_registry: Optional[IntegrationRegistry] = None,
                 system_settings=None, mcp_registry=None, docdb_registry=None):
        self.config = config
        self._registry = agent_registry
        self._integration_registry = integration_registry
        self._mcp_registry = mcp_registry
        self._docdb_registry = docdb_registry
        self._settings = system_settings
        self._semaphore = asyncio.Semaphore(config.max_concurrent_agents)
        self._ctrl_client = build_client(config.controller)
        self._ctrl_client_key = self._client_key(config.controller)
        logger.info("Controller ready: %s / %s", config.controller.provider, config.controller.model)

    @staticmethod
    def _client_key(cfg) -> str:
        return f"{cfg.provider}|{cfg.model}|{cfg.base_url}|{cfg.api_key}"

    def _get_ctrl_client(self):
        if self._settings is None:
            return self._ctrl_client
        cfg = self._settings.controller_as_config()
        key = self._client_key(cfg)
        if key != self._ctrl_client_key:
            self._ctrl_client = build_client(cfg)
            self._ctrl_client_key = key
            logger.info("Controller client rebuilt → %s / %s", cfg.provider, cfg.model)
        return self._ctrl_client

    def _get_tools(self) -> list[dict]:
        """Return combined tool definitions from HTTP integrations + MCP + DocDB."""
        http_tools  = self._integration_registry.to_tool_definitions() if self._integration_registry else []
        mcp_tools   = self._mcp_registry.to_tool_definitions()         if self._mcp_registry  else []
        docdb_tools = self._docdb_registry.to_tool_definitions()       if self._docdb_registry else []
        return http_tools + mcp_tools + docdb_tools

    def _get_tool_executor(self) -> Optional[ToolExecutor]:
        if self._integration_registry:
            return ToolExecutor(self._integration_registry, self._mcp_registry, self._docdb_registry)
        return None

    def _get_prompts(self):
        if self._settings:
            return self._settings.prompts
        from system_settings import PromptSettings
        return PromptSettings()

    @property
    def _agents(self):
        return self._registry.agents

    # ── Public ────────────────────────────────────────────────────────────────

    async def run(self, request: OrchestratorRequest,
                  document_chunks: list[DocumentChunk] | None = None) -> OrchestratorResponse:
        t0 = time.monotonic()
        chunks = document_chunks or []
        logger.info("Session %s started", request.session_id)

        sub_tasks = await self._decompose(request.prompt, chunks)
        if not sub_tasks:
            return OrchestratorResponse(session_id=request.session_id,
                                        status=TaskStatus.FAILED, error="No sub-tasks generated")

        responses = await self._dispatch(sub_tasks)
        final = await self._synthesise(request.prompt, responses)

        return OrchestratorResponse(
            session_id=request.session_id, status=TaskStatus.COMPLETED,
            final_answer=final, sub_task_count=len(sub_tasks),
            agent_responses=responses, total_duration_seconds=time.monotonic() - t0,
        )

    # ── Step 1: Decompose — plain completion, output JSON only ────────────────

    async def _decompose(self, prompt: str, chunks: list[DocumentChunk]) -> list[SubTask]:
        agents = self._agents
        if not agents:
            return []

        p = self._get_prompts()
        desc = "\n".join(
            f"  {aid}: {w.config.provider}/{w.config.model}"
            for aid, w in agents.items()
        )
        doc_summary = f"{len(chunks)} chunk(s)" if chunks else "none"

        # Decompose prompt does NOT include tool descriptions —
        # the controller just needs to split the work into sub-tasks.
        decompose_sys = p.decompose_system.format(agent_descriptions=desc)

        messages = [
            LLMMessage(role="system", content=decompose_sys),
            LLMMessage(role="user", content=f"User request: {prompt}\nDocuments: {doc_summary}\nDecompose now."),
        ]

        try:
            raw = (await self._get_ctrl_client().complete(messages)).content.strip()
            # Strip markdown fences if the model wraps JSON in ```
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            task_defs = json.loads(raw.strip())
        except Exception as exc:
            logger.error("Decompose failed: %s — single-task fallback", exc)
            task_defs = [{"agent_id": next(iter(agents)), "role": "general",
                          "instruction": prompt, "needs_docs": bool(chunks)}]

        result = []
        for td in task_defs:
            aid = td.get("agent_id", next(iter(agents)))
            if aid not in agents:
                aid = next(iter(agents))
            result.append(SubTask(
                agent_id=aid,
                role=AgentRole(td.get("role", "general")),
                instruction=td.get("instruction", prompt),
                document_chunks=chunks if td.get("needs_docs") else [],
            ))
        return result

    # ── Step 2: Dispatch — each worker runs the tool loop ─────────────────────

    async def _dispatch(self, tasks: list[SubTask]) -> list[AgentResponse]:
        tools = self._get_tools()
        executor = self._get_tool_executor()
        p = self._get_prompts()

        if tools:
            logger.info("Dispatching %d task(s) with %d tool(s) available", len(tasks), len(tools))
        else:
            logger.info("Dispatching %d task(s) with no tools (add integrations to enable)", len(tasks))

        async def _run(task):
            async with self._semaphore:
                worker = self._agents.get(task.agent_id)
                if not worker:
                    return AgentResponse(task_id=task.task_id, agent_id=task.agent_id,
                                         status=TaskStatus.FAILED, error="Agent not found")
                return await worker.execute(
                    task,
                    tool_executor=executor if tools else None,
                    tools=tools if tools else None,
                    global_system=p.global_agent_system,
                    role_prompts=p.role_prompts,
                )

        return list(await asyncio.gather(*[_run(t) for t in tasks]))

    # ── Step 3: Synthesise — plain completion ─────────────────────────────────

    async def _synthesise(self, prompt: str, responses: list[AgentResponse]) -> str:
        p = self._get_prompts()

        results = "\n\n".join(
            f"--- {r.agent_id} ({r.status}) ---\n{r.result or '[ERROR: ' + str(r.error) + ']'}"
            for r in responses
        )

        # Surface which tools were actually used so the synthesiser has context
        tool_info = []
        for r in responses:
            if r.metadata and r.metadata.get("tool_trace"):
                for t in r.metadata["tool_trace"]:
                    tool_info.append(
                        f"  [{r.agent_id}] called {t['tool']}({json.dumps(t['arguments'])}) "
                        f"→ {t['result'][:300]}"
                    )
        tool_section = ("\n\nTools called during research:\n" + "\n".join(tool_info)) if tool_info else ""

        messages = [
            LLMMessage(role="system", content=p.synthesis_system),
            LLMMessage(role="user", content=(
                f"Original request:\n{prompt}"
                f"{tool_section}\n\n"
                f"Agent results:\n{results}\n\n"
                "Write the final response."
            )),
        ]
        try:
            return (await self._get_ctrl_client().complete(messages)).content
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            return "## Results\n\n" + results
