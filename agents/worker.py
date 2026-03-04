"""
agents/worker.py — Worker LLM Agent.

Each WorkerAgent:
  1. Holds a reference to one BaseLLMClient (provider-agnostic).
  2. Receives a SubTask from the Controller.
  3. Builds a prompt that includes any document chunks.
  4. Calls its LLM client and returns an AgentResponse.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from api_clients.base import BaseLLMClient, LLMMessage
from config import AgentConfig
from schemas import AgentResponse, SubTask, TaskStatus

logger = logging.getLogger(__name__)

# Role-specific system prompt prefixes
_ROLE_PROMPTS: dict[str, str] = {
    "researcher":  "You are a meticulous researcher. Gather facts, cite sources when possible, and be thorough.",
    "summarizer":  "You are a precise summarizer. Condense information clearly without losing key details.",
    "analyst":     "You are a critical analyst. Examine data, spot patterns, and provide structured insights.",
    "writer":      "You are a skilled writer. Produce clear, engaging, well-structured content.",
    "critic":      "You are a constructive critic. Identify weaknesses, inconsistencies, and areas for improvement.",
    "coder":       "You are an expert software engineer. Write clean, well-commented, production-ready code.",
    "general":     "You are a helpful, knowledgeable assistant.",
}


class WorkerAgent:
    """
    An independent worker that executes a single SubTask using its assigned LLM.
    """

    def __init__(self, config: AgentConfig, client: BaseLLMClient):
        self.config = config
        self.client = client
        self.agent_id = config.agent_id
        logger.info(
            "WorkerAgent '%s' ready  provider=%s  model=%s",
            self.agent_id, config.provider, config.model,
        )

    # ------------------------------------------------------------------
    # Main execution path
    # ------------------------------------------------------------------

    async def execute(self, task: SubTask) -> AgentResponse:
        """Process a SubTask and return an AgentResponse."""
        logger.info(
            "Agent '%s' starting task %s (role=%s)",
            self.agent_id, task.task_id, task.role,
        )
        start = time.monotonic()

        try:
            messages = self._build_messages(task)
            llm_response = await self.client.complete(messages)

            duration = time.monotonic() - start
            logger.info(
                "Agent '%s' finished task %s in %.2fs",
                self.agent_id, task.task_id, duration,
            )
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.COMPLETED,
                result=llm_response.content,
                token_usage={
                    "input": llm_response.input_tokens,
                    "output": llm_response.output_tokens,
                },
                duration_seconds=duration,
                metadata={
                    "model": llm_response.model,
                    "provider": llm_response.provider,
                    "finish_reason": llm_response.finish_reason,
                },
            )

        except Exception as exc:
            duration = time.monotonic() - start
            logger.error(
                "Agent '%s' failed task %s after %.2fs: %s",
                self.agent_id, task.task_id, duration, exc,
            )
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error=str(exc),
                duration_seconds=duration,
            )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_messages(self, task: SubTask) -> list[LLMMessage]:
        """
        Assemble the message list for the LLM call:
          1. System message (role persona)
          2. Optional context from the Controller
          3. Document chunks (if any)
          4. The actual instruction
        """
        role_prompt = _ROLE_PROMPTS.get(task.role.value, _ROLE_PROMPTS["general"])
        system_prompt = (
            f"{role_prompt}\n\n"
            "Respond only with the content requested. "
            "Be concise unless depth is explicitly required."
        )

        user_parts: list[str] = []

        # Controller context (e.g. results from other agents or original prompt)
        if task.context:
            user_parts.append(f"## Context\n{task.context}")

        # Document chunks
        if task.document_chunks:
            doc_sections: list[str] = []
            for chunk in task.document_chunks:
                header = (
                    f"### Document: {chunk.filename}  "
                    f"(chunk {chunk.chunk_index + 1}/{chunk.total_chunks})"
                )
                doc_sections.append(f"{header}\n{chunk.text}")
            user_parts.append("## Provided Documents\n\n" + "\n\n---\n\n".join(doc_sections))

        # The task instruction
        user_parts.append(f"## Your Task\n{task.instruction}")

        return [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content="\n\n".join(user_parts)),
        ]
