"""
controller.py — Main Controller LLM.

Responsibilities
----------------
1. Receive the user's prompt + optional document chunks.
2. Call the Controller LLM to decompose the task into SubTasks.
3. Dispatch SubTasks to WorkerAgents concurrently (asyncio.gather).
4. Collect AgentResponses.
5. Call the Controller LLM again to synthesise a final answer.
6. Return an OrchestratorResponse.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from api_clients import BaseLLMClient, LLMMessage, build_client
from agents.worker import WorkerAgent
from config import AppConfig, AgentConfig
from schemas import (
    AgentResponse,
    AgentRole,
    DocumentChunk,
    OrchestratorRequest,
    OrchestratorResponse,
    SubTask,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decomposition prompt template
# ---------------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """
You are the orchestration controller of a multi-agent AI system.
Your job is to break a user's request into focused sub-tasks, one per available agent.

Available agents (id → description):
{agent_descriptions}

Respond ONLY with a valid JSON array. Each element must have these keys:
  - "agent_id"    : string  — must be one of the available agent IDs
  - "role"        : string  — one of: researcher, summarizer, analyst, writer, critic, coder, general
  - "instruction" : string  — specific, self-contained instruction for that agent
  - "needs_docs"  : boolean — whether this agent should receive the uploaded documents

Example:
[
  {{"agent_id": "agent-1", "role": "researcher", "instruction": "Find key facts about X", "needs_docs": false}},
  {{"agent_id": "agent-2", "role": "summarizer", "instruction": "Summarise the document", "needs_docs": true}}
]

Rules:
- Only assign to agent IDs from the list above.
- If there is only one agent, still output a JSON array with one element.
- Do NOT output anything outside the JSON array.
""".strip()

_DECOMPOSE_USER = """
User request: {prompt}

Documents uploaded: {doc_summary}

Decompose this request into sub-tasks now.
""".strip()

# ---------------------------------------------------------------------------
# Synthesis prompt template
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """
You are the orchestration controller synthesising final results.
You will receive the outputs from multiple specialised agents.
Your task: produce one cohesive, high-quality final answer for the user.
Do not mention agents or internal orchestration mechanics.
""".strip()

_SYNTHESIS_USER = """
Original user request:
{prompt}

Agent results:
{results}

Now write the final consolidated response.
""".strip()


class MainController:
    """
    Orchestrates task decomposition, agent dispatching, and response synthesis.
    """

    def __init__(self, config: AppConfig):
        self.config = config

        # Build controller LLM client
        self._ctrl_client: BaseLLMClient = build_client(config.controller)
        logger.info(
            "Controller LLM: provider=%s model=%s",
            config.controller.provider, config.controller.model,
        )

        # Build worker agents (id → WorkerAgent)
        self._agents: dict[str, WorkerAgent] = {}
        for agent_cfg in config.agents:
            client = build_client(agent_cfg)
            self._agents[agent_cfg.agent_id] = WorkerAgent(agent_cfg, client)

        if not self._agents:
            raise RuntimeError("No worker agents configured")

        self._semaphore = asyncio.Semaphore(config.max_concurrent_agents)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        request: OrchestratorRequest,
        document_chunks: list[DocumentChunk] | None = None,
    ) -> OrchestratorResponse:
        """
        Full orchestration pipeline: decompose → dispatch → synthesise.
        """
        overall_start = time.monotonic()
        document_chunks = document_chunks or []

        logger.info("=== Session %s started ===", request.session_id)

        # 1. Decompose task
        sub_tasks = await self._decompose(request.prompt, document_chunks)

        if not sub_tasks:
            return OrchestratorResponse(
                session_id=request.session_id,
                status=TaskStatus.FAILED,
                error="Controller returned no sub-tasks",
            )

        logger.info("Decomposed into %d sub-task(s)", len(sub_tasks))

        # 2. Dispatch concurrently
        agent_responses = await self._dispatch(sub_tasks)

        # 3. Synthesise
        final_answer = await self._synthesise(request.prompt, agent_responses)

        elapsed = time.monotonic() - overall_start
        logger.info("=== Session %s completed in %.2fs ===", request.session_id, elapsed)

        return OrchestratorResponse(
            session_id=request.session_id,
            status=TaskStatus.COMPLETED,
            final_answer=final_answer,
            sub_task_count=len(sub_tasks),
            agent_responses=agent_responses,
            total_duration_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Step 1: Decompose
    # ------------------------------------------------------------------

    async def _decompose(
        self, prompt: str, chunks: list[DocumentChunk]
    ) -> list[SubTask]:
        agent_descriptions = "\n".join(
            f"  {aid}: {self._agents[aid].config.provider}/{self._agents[aid].config.model}"
            for aid in self._agents
        )
        doc_summary = (
            f"{len(chunks)} chunk(s) from {len({c.filename for c in chunks})} file(s)"
            if chunks else "none"
        )

        messages = [
            LLMMessage(
                role="system",
                content=_DECOMPOSE_SYSTEM.format(agent_descriptions=agent_descriptions),
            ),
            LLMMessage(
                role="user",
                content=_DECOMPOSE_USER.format(prompt=prompt, doc_summary=doc_summary),
            ),
        ]

        try:
            response = await self._ctrl_client.complete(messages)
            raw_json = response.content.strip()
            # Strip potential markdown fences
            if raw_json.startswith("```"):
                raw_json = raw_json.split("```")[1]
                if raw_json.startswith("json"):
                    raw_json = raw_json[4:]
            task_defs: list[dict] = json.loads(raw_json)
        except Exception as exc:
            logger.error("Decomposition failed: %s", exc)
            # Fallback: assign everything to the first available agent
            task_defs = [{
                "agent_id": next(iter(self._agents)),
                "role": "general",
                "instruction": prompt,
                "needs_docs": bool(chunks),
            }]

        sub_tasks: list[SubTask] = []
        for td in task_defs:
            agent_id = td.get("agent_id", next(iter(self._agents)))
            if agent_id not in self._agents:
                logger.warning("Unknown agent_id '%s', reassigning to first agent", agent_id)
                agent_id = next(iter(self._agents))

            task_chunks = chunks if td.get("needs_docs", False) else []

            sub_tasks.append(SubTask(
                agent_id=agent_id,
                role=AgentRole(td.get("role", "general")),
                instruction=td["instruction"],
                context=None,
                document_chunks=task_chunks,
            ))

        return sub_tasks

    # ------------------------------------------------------------------
    # Step 2: Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, sub_tasks: list[SubTask]) -> list[AgentResponse]:
        async def _run_with_semaphore(task: SubTask) -> AgentResponse:
            async with self._semaphore:
                agent = self._agents.get(task.agent_id)
                if not agent:
                    return AgentResponse(
                        task_id=task.task_id,
                        agent_id=task.agent_id,
                        status=TaskStatus.FAILED,
                        error=f"Agent '{task.agent_id}' not found",
                    )
                return await agent.execute(task)

        responses = await asyncio.gather(
            *[_run_with_semaphore(t) for t in sub_tasks],
            return_exceptions=False,
        )
        return list(responses)

    # ------------------------------------------------------------------
    # Step 3: Synthesise
    # ------------------------------------------------------------------

    async def _synthesise(
        self, original_prompt: str, responses: list[AgentResponse]
    ) -> str:
        results_text = "\n\n".join(
            f"--- Agent {r.agent_id} ({r.status}) ---\n"
            + (r.result or f"[ERROR: {r.error}]")
            for r in responses
        )

        messages = [
            LLMMessage(role="system", content=_SYNTHESIS_SYSTEM),
            LLMMessage(
                role="user",
                content=_SYNTHESIS_USER.format(
                    prompt=original_prompt, results=results_text
                ),
            ),
        ]

        try:
            response = await self._ctrl_client.complete(messages)
            return response.content
        except Exception as exc:
            logger.error("Synthesis failed: %s", exc)
            # Graceful fallback: concatenate agent results
            return "## Aggregated Agent Results\n\n" + results_text
