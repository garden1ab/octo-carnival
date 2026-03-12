"""
agents/worker.py — Worker LLM Agent v5 with agentic tool loop.

When integrations are enabled, the agent runs a tool-calling loop:
  ask LLM → LLM requests tool → execute real API → feed result → repeat → final answer.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from api_clients.base import BaseLLMClient, LLMMessage
from api_integrations.tool_executor import ToolExecutor
from config import AgentConfig
from schemas import AgentResponse, SubTask, TaskStatus
from tool_loop import run_with_tools

logger = logging.getLogger(__name__)

_DEFAULT_ROLE_PROMPTS: dict[str, str] = {
    "researcher": "You are a meticulous researcher. Gather facts, cite sources when possible, and be thorough.",
    "summarizer": "You are a precise summarizer. Condense information clearly without losing key details.",
    "analyst":    "You are a critical analyst. Examine data, spot patterns, and provide structured insights.",
    "writer":     "You are a skilled writer. Produce clear, engaging, well-structured content.",
    "critic":     "You are a constructive critic. Identify weaknesses, inconsistencies, and areas for improvement.",
    "coder":      "You are an expert software engineer. Write clean, well-commented, production-ready code.",
    "general":    "You are a helpful, knowledgeable assistant.",
}

_DEFAULT_GLOBAL_SYSTEM = (
    "Respond only with the content requested. "
    "Be concise unless depth is required. "
    "Format responses in clear markdown."
)


class WorkerAgent:
    def __init__(self, config: AgentConfig, client: BaseLLMClient):
        self.config = config
        self.client = client
        self.agent_id = config.agent_id
        logger.info("WorkerAgent '%s' ready  provider=%s  model=%s",
                    self.agent_id, config.provider, config.model)

    async def execute(
        self,
        task: SubTask,
        tool_executor: Optional[ToolExecutor] = None,
        tools: Optional[list[dict]] = None,
        global_system: str = "",
        role_prompts: Optional[dict[str, str]] = None,
    ) -> AgentResponse:
        logger.info("Agent '%s' starting task %s (role=%s)", self.agent_id, task.task_id, task.role)
        start = time.monotonic()
        try:
            messages = self._build_messages(task, global_system, role_prompts)

            if tool_executor and tools:
                # ── Agentic tool loop ──────────────────────────────────────────
                content, tool_trace = await run_with_tools(
                    self.client, messages, tool_executor, tools
                )
                metadata = {"tool_calls": len(tool_trace), "tool_trace": tool_trace}
            else:
                # ── Plain completion (no tools configured) ─────────────────────
                resp = await self.client.complete(messages)
                content = resp.content
                metadata = {"model": resp.model, "provider": resp.provider}

            duration = time.monotonic() - start
            logger.info("Agent '%s' finished task %s in %.2fs (tool_calls=%d)",
                        self.agent_id, task.task_id, duration, len(metadata.get("tool_trace", [])))

            return AgentResponse(
                task_id=task.task_id, agent_id=self.agent_id,
                status=TaskStatus.COMPLETED, result=content,
                duration_seconds=duration, metadata=metadata,
            )
        except Exception as exc:
            duration = time.monotonic() - start
            logger.error("Agent '%s' failed: %s", self.agent_id, exc)
            return AgentResponse(task_id=task.task_id, agent_id=self.agent_id,
                                 status=TaskStatus.FAILED, error=str(exc), duration_seconds=duration)

    def _build_messages(
        self,
        task: SubTask,
        global_system: str,
        role_prompts: Optional[dict[str, str]],
    ) -> list[LLMMessage]:
        prompts = role_prompts or _DEFAULT_ROLE_PROMPTS
        persona = prompts.get(task.role.value) or _DEFAULT_ROLE_PROMPTS.get(task.role.value, _DEFAULT_ROLE_PROMPTS["general"])
        suffix = global_system.strip() if global_system.strip() else _DEFAULT_GLOBAL_SYSTEM
        system_prompt = f"{persona}\n\n{suffix}"

        user_parts: list[str] = []
        if task.context:
            user_parts.append(f"## Context\n{task.context}")
        if task.document_chunks:
            doc_sections = [
                f"### Document: {c.filename} (chunk {c.chunk_index + 1}/{c.total_chunks})\n{c.text}"
                for c in task.document_chunks
            ]
            user_parts.append("## Provided Documents\n\n" + "\n\n---\n\n".join(doc_sections))
        user_parts.append(f"## Your Task\n{task.instruction}")

        return [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content="\n\n".join(user_parts)),
        ]
