"""
api_clients/tool_json_fallback.py
Prompt-engineering based tool calling for models without native function calling.
Used by Ollama and any local model that doesn't support tool_choice='auto'.

The prompt is written to be very literal and forceful — local models need
explicit "stop and output the XML" instructions, otherwise they narrate
what they would search for rather than actually calling the tool.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from api_clients.base import LLMMessage, ToolCall

logger = logging.getLogger(__name__)

_TOOL_SYSTEM_BLOCK = """
=== TOOL USE INSTRUCTIONS ===

You have access to real external tools that can fetch live data. When you need
information you don't have, you MUST call a tool — do NOT make up data.

To call a tool, output ONLY this XML block (no other text on the same turn):

<tool_call>
{"name": "TOOL_NAME", "arguments": {ARGUMENTS_AS_JSON}}
</tool_call>

You will then receive a <tool_result> block with the real API response.
After receiving tool results, use that data to write your answer.

You may call tools multiple times in sequence if needed.

=== AVAILABLE TOOLS ===

{tool_definitions}

=== RULES ===
1. If the task requires current/live data (news, weather, prices, etc.) — call a tool.
2. Output ONLY the <tool_call> block when calling a tool. No explanation before it.
3. Never fabricate tool results. Wait for the <tool_result> block.
4. After receiving results, write your actual answer (no more tool calls needed).
""".strip()


def inject_tools_into_messages(
    messages: list[LLMMessage],
    tools: list[dict],
) -> list[LLMMessage]:
    """Prepend tool instructions to the system message."""
    tool_lines = []
    for t in tools:
        props = t.get("input_schema", {}).get("properties", {})
        args_desc = ", ".join(
            f'"{k}": "{v.get("description", k)}"'
            for k, v in props.items()
        )
        tool_lines.append(
            f'- Name: {t["name"]}\n'
            f'  Description: {t.get("description", "")}\n'
            f'  Arguments: {{{args_desc}}}'
        )
    injection = _TOOL_SYSTEM_BLOCK.format(tool_definitions="\n\n".join(tool_lines))

    result = []
    injected = False
    for msg in messages:
        if msg.role == "system" and not injected:
            result.append(LLMMessage(role="system", content=f"{msg.content}\n\n{injection}"))
            injected = True
        else:
            result.append(msg)

    if not injected:
        result.insert(0, LLMMessage(role="system", content=injection))

    return result


def extract_tool_calls_from_text(text: str) -> list[ToolCall]:
    """Parse <tool_call>...</tool_call> blocks from model output."""
    pattern = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    calls: list[ToolCall] = []
    for match in pattern.finditer(text):
        try:
            payload: dict[str, Any] = json.loads(match.group(1))
            name = payload.get("name", "")
            arguments = payload.get("arguments", {})
            if name:
                calls.append(ToolCall(
                    call_id=f"tc-{uuid.uuid4().hex[:8]}",
                    name=name,
                    arguments=arguments if isinstance(arguments, dict) else {},
                ))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse <tool_call>: %s", exc)
    return calls


def format_tool_result_for_text(call_id: str, name: str, content: str) -> str:
    """Format a tool result for injection back as a user message."""
    return (
        f"<tool_result>\n"
        f'{{"call_id": "{call_id}", "tool": "{name}", "result": {json.dumps(content)}}}\n'
        f"</tool_result>\n\n"
        f"Now use the above data to complete your task."
    )
