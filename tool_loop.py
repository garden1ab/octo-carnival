"""
tool_loop.py — Provider-agnostic agentic tool execution loop.

Fixes in this version:
- Anthropic: passes raw SDK content blocks back correctly (required by the API)
- OpenAI/local: uses proper assistant + tool message format
- Ollama fallback: uses <tool_call> text injection
- All paths: parallel tool execution, capped at max_iterations
"""

from __future__ import annotations

import json
import logging
from typing import Any

from api_clients.base import BaseLLMClient, LLMMessage, LLMResponse, ToolCall, ToolResult
from api_integrations.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 6


async def run_with_tools(
    client: BaseLLMClient,
    messages: list[LLMMessage],
    tool_executor: ToolExecutor,
    tools: list[dict],
    max_iterations: int = _MAX_TOOL_ITERATIONS,
) -> tuple[str, list[dict]]:
    """
    Run the agentic tool loop. Returns (final_answer_text, tool_trace).
    tool_trace is a list of {tool, arguments, result} dicts for display.
    """
    if not tools:
        resp = await client.complete(messages)
        return resp.content, []

    tool_trace: list[dict] = []

    # Each provider needs its own conversation state format
    if client.provider == "anthropic":
        return await _loop_anthropic(client, messages, tool_executor, tools, tool_trace, max_iterations)
    elif client.provider in ("openai", "openai_compat"):
        return await _loop_openai(client, messages, tool_executor, tools, tool_trace, max_iterations)
    else:
        # local / ollama — use text-based fallback
        return await _loop_text_fallback(client, messages, tool_executor, tools, tool_trace, max_iterations)


# ── Anthropic native tool_use loop ────────────────────────────────────────────

async def _loop_anthropic(client, messages, tool_executor, tools, tool_trace, max_iterations):
    """
    Anthropic requires the exact content blocks from the assistant message
    to be echoed back when submitting tool_results. We carry a native
    conversation list (list[dict]) alongside our LLMMessage list.
    """
    import anthropic as _anthropic

    # Extract system and build initial convo
    system_parts = [m.content for m in messages if m.role == "system"]
    system = "\n\n".join(system_parts) if system_parts else _anthropic.NOT_GIVEN
    convo: list[dict] = [{"role": m.role, "content": m.content}
                          for m in messages if m.role != "system"]

    anthropic_tools = [
        {"name": t["name"], "description": t.get("description", ""),
         "input_schema": t.get("input_schema", {"type": "object", "properties": {}})}
        for t in tools
    ]

    for iteration in range(max_iterations):
        resp = await client._client.messages.create(
            model=client.model,
            max_tokens=client.max_tokens,
            temperature=client.temperature,
            system=system,
            messages=convo,
            tools=anthropic_tools,
        )

        # Check for tool_use blocks
        tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]

        if not tool_use_blocks or resp.stop_reason != "tool_use":
            # Done — extract text
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return text, tool_trace

        # Append assistant message with full content blocks (required by Anthropic)
        convo.append({"role": "assistant", "content": resp.content})

        # Execute tools and build tool_result blocks
        tool_result_content = []
        for block in tool_use_blocks:
            args = dict(block.input) if block.input else {}
            result_text = await tool_executor.execute(block.name, args)
            tool_trace.append({"tool": block.name, "arguments": args,
                                "result": result_text[:500] + ("…" if len(result_text) > 500 else "")})
            logger.info("  [anthropic tool] %s → %d chars", block.name, len(result_text))
            tool_result_content.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        convo.append({"role": "user", "content": tool_result_content})

    # Max iterations hit
    logger.warning("Anthropic tool loop hit max_iterations=%d", max_iterations)
    final = await client._client.messages.create(
        model=client.model, max_tokens=client.max_tokens,
        temperature=client.temperature, system=system, messages=convo,
    )
    return "".join(b.text for b in final.content if hasattr(b, "text")), tool_trace


# ── OpenAI native function calling loop ───────────────────────────────────────

async def _loop_openai(client, messages, tool_executor, tools, tool_trace, max_iterations):
    """OpenAI / OpenAI-compat: uses tool role messages."""
    oai_tools = [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
        }}
        for t in tools
    ]
    convo: list[dict] = [{"role": m.role, "content": m.content} for m in messages]

    for iteration in range(max_iterations):
        try:
            resp = await client._client.chat.completions.create(
                model=client.model, messages=convo,
                max_tokens=client.max_tokens, temperature=client.temperature,
                tools=oai_tools, tool_choice="auto",
            )
        except Exception as exc:
            # Model doesn't support tools — fall back
            logger.warning("[openai] native tools failed (%s), using text fallback", exc)
            return await _loop_text_fallback(client, messages, tool_executor, tools, tool_trace, max_iterations)

        choice = resp.choices[0]
        msg = choice.message

        if not msg.tool_calls or choice.finish_reason != "tool_calls":
            return msg.content or "", tool_trace

        # Append assistant message with tool_calls
        convo.append(msg.model_dump())

        # Execute and append tool results
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result_text = await tool_executor.execute(tc.function.name, args)
            tool_trace.append({"tool": tc.function.name, "arguments": args,
                                "result": result_text[:500] + ("…" if len(result_text) > 500 else "")})
            logger.info("  [openai tool] %s → %d chars", tc.function.name, len(result_text))
            convo.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})

    logger.warning("OpenAI tool loop hit max_iterations=%d", max_iterations)
    final = await client._client.chat.completions.create(
        model=client.model, messages=convo,
        max_tokens=client.max_tokens, temperature=client.temperature,
    )
    return final.choices[0].message.content or "", tool_trace


# ── Text / prompt-engineering fallback (Ollama + any model) ──────────────────

async def _loop_text_fallback(client, messages, tool_executor, tools, tool_trace, max_iterations):
    """
    Works with any model that can follow instructions.
    Injects tool schemas as text, detects <tool_call> blocks in responses,
    executes the real HTTP call, injects <tool_result> back, repeats.
    """
    from api_clients.tool_json_fallback import (
        inject_tools_into_messages,
        extract_tool_calls_from_text,
        format_tool_result_for_text,
    )

    # Inject tool definitions into system prompt once
    conversation = inject_tools_into_messages(messages, tools)

    for iteration in range(max_iterations):
        resp = await client.complete(conversation)
        tool_calls = extract_tool_calls_from_text(resp.content)

        if not tool_calls:
            # Strip any leftover XML tags from final answer
            import re
            clean = re.sub(r"<tool_call>.*?</tool_call>", "", resp.content, flags=re.DOTALL).strip()
            return clean, tool_trace

        # Append assistant turn
        conversation.append(LLMMessage(role="assistant", content=resp.content))

        # Execute tools and build result message
        result_parts = []
        for tc in tool_calls:
            result_text = await tool_executor.execute(tc.name, tc.arguments)
            tool_trace.append({"tool": tc.name, "arguments": tc.arguments,
                                "result": result_text[:500] + ("…" if len(result_text) > 500 else "")})
            logger.info("  [text-fallback tool] %s → %d chars", tc.name, len(result_text))
            result_parts.append(format_tool_result_for_text(tc.call_id, tc.name, result_text))

        conversation.append(LLMMessage(role="user", content="\n\n".join(result_parts)))

    logger.warning("Text fallback tool loop hit max_iterations=%d", max_iterations)
    final = await client.complete(conversation)
    return final.content, tool_trace
