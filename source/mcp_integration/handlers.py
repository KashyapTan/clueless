"""
MCP tool call handlers.

Handles the execution of MCP tool calls from Ollama responses.
"""

import json
import asyncio
import time
from typing import List, Dict, Any, Optional

from ollama import chat

from .manager import mcp_manager
from .retriever import retriever
from .terminal_executor import is_terminal_tool, execute_terminal_tool
from ..core.connection import broadcast_message
from ..core.state import app_state
from ..core.thread_pool import run_in_thread


def _extract_response(response) -> Optional[Dict[str, Any]]:
    """
    Extract content, thinking, and token stats from an Ollama response object.

    Works for both the initial tool-detection call (no tools needed) and
    the final call after tool execution completes.
    """
    content = ""
    thinking = ""
    token_stats = {"prompt_eval_count": 0, "eval_count": 0}

    if hasattr(response, "message") and response.message:
        msg = response.message
        if hasattr(msg, "content") and msg.content:
            content = msg.content
        if hasattr(msg, "thinking") and msg.thinking:
            thinking = msg.thinking

    # Extract token stats from top-level response attributes
    if hasattr(response, "prompt_eval_count"):
        token_stats["prompt_eval_count"] = (
            getattr(response, "prompt_eval_count", 0) or 0
        )
    if hasattr(response, "eval_count"):
        token_stats["eval_count"] = getattr(response, "eval_count", 0) or 0

    if content or thinking:
        return {"content": content, "thinking": thinking, "token_stats": token_stats}
    return None


async def handle_mcp_tool_calls(
    messages: List[Dict[str, Any]], image_paths: List[str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Check for and execute MCP tool calls from Ollama.

    Makes a non-streamed call with think=False to detect tool requests
    (workaround for Ollama bug #10976: think+tools=empty output).
    If tools are needed, executes them via MCP servers and loops until done.

    Always returns pre_computed_response=None so the caller falls through
    to the streaming path for proper token-by-token response delivery.

    Args:
        messages: The conversation message history
        image_paths: List of image paths attached to the query

    Returns:
        (updated_messages, tool_calls_made, pre_computed_response)
        - updated_messages: the messages list with tool exchanges appended
        - tool_calls_made: list of {name, args, result, server} for UI display
        - pre_computed_response: always None (caller streams the final response)
    """
    tool_calls_made = []

    if not mcp_manager.has_tools():
        return messages, tool_calls_made, None

    # Only do tool detection for text-only queries (no images)
    # Vision models + tool calling don't always mix well
    has_images = any(msg.get("images") for msg in messages) or bool(image_paths)
    if has_images:
        return messages, tool_calls_made, None

    # Retrieve relevant tools
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    # Get settings
    from ..database import db
    always_on_json = db.get_setting("tool_always_on")
    always_on = []
    if always_on_json:
        try:
            always_on = json.loads(always_on_json)
        except:
            pass

    top_k_str = db.get_setting("tool_retriever_top_k")
    top_k = int(top_k_str) if top_k_str else 5

    all_tools = mcp_manager.get_ollama_tools() or []

    # Filter tools using the retriever
    filtered_tools = retriever.retrieve_tools(
        query=user_query, all_tools=all_tools, always_on=always_on, top_k=top_k
    )

    if len(filtered_tools) < len(all_tools):
        print(
            f"[MCP] Retriever selected {len(filtered_tools)}/{len(all_tools)} tools for query: '{user_query[:30]}...'"
        )

    # Non-streamed call to detect tool requests
    # think=False works around Ollama bug #10976 (think+tools=empty output)
    # Use run_in_thread to avoid blocking the event loop (critical for thinking models)
    try:
        response = await run_in_thread(
            chat,
            model=app_state.selected_model,
            messages=messages,
            tools=filtered_tools,
            think=False,
        )
    except Exception as e:
        print(f"[MCP] Error in tool detection call: {e}")
        return messages, tool_calls_made, None

    # If no tool calls detected, return None for pre_computed_response so the

    # caller falls through to the streaming path for proper token-by-token delivery.
    if not response.message.tool_calls:
        return messages, tool_calls_made, None

    # Loop: keep calling tools until Ollama gives a final text answer
    from ..config import MAX_MCP_TOOL_ROUNDS

    rounds = 0

    while response.message.tool_calls and rounds < MAX_MCP_TOOL_ROUNDS:
        rounds += 1

        # ── Stop check: abort tool loop when user presses stop ──
        if app_state.stop_streaming:
            print("[MCP] Stop requested — aborting tool call loop")
            break

        # Add the Assistant's message (requesting tools) to history ONCE for this turn
        # Strip thinking content from the assistant message to avoid confusing follow-up calls
        # Only keep essential fields: role, content, tool_calls
        raw_msg = response.message
        assistant_msg = {
            "role": "assistant",
            "content": raw_msg.content or "",
        }
        if hasattr(raw_msg, "tool_calls") and raw_msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in raw_msg.tool_calls
            ]

        messages.append(assistant_msg)

        # Process all tool calls in this turn
        for tool_call in response.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments
            server_name = mcp_manager.get_tool_server_name(fn_name)

            print(f"[MCP] Tool call: {fn_name}({fn_args}) from server '{server_name}'")

            # Check stop before each tool execution
            if app_state.stop_streaming:
                print("[MCP] Stop requested — skipping tool call")
                break

            # ── Terminal tool interception ──────────────────────────────
            # Handle terminal tools with approval/session logic directly
            # (no MCP subprocess needed).
            if is_terminal_tool(fn_name, server_name):
                result = await execute_terminal_tool(fn_name, fn_args, server_name)
            else:
                # ── Standard tool execution ─────────────────────────────

                # Broadcast to UI so users see the tool being called
                await broadcast_message(
                    "tool_call",
                    json.dumps(
                        {
                            "name": fn_name,
                            "args": fn_args,
                            "server": server_name,
                            "status": "calling",
                        }
                    ),
                )

                # Execute the tool via MCP
                try:
                    result = await mcp_manager.call_tool(fn_name, dict(fn_args))
                except Exception as e:
                    result = f"Error executing tool: {e}"

            print(f"[MCP] Tool result:\n{str(result)[0:100]}...")

            # Truncate result if it's excessively large (e.g. > 100k chars) to prevent context window overflow
            result_str = str(result)
            if len(result_str) > 100000:
                print(
                    f"[MCP] Truncating large tool output ({len(result_str)} chars) to 100k chars"
                )
                result_str = (
                    result_str[:100000] + "... [Output truncated due to length]"
                )

            # Broadcast result to UI
            await broadcast_message(
                "tool_call",
                json.dumps(
                    {
                        "name": fn_name,
                        "args": fn_args,
                        "result": result_str,
                        "server": server_name,
                        "status": "complete",
                    }
                ),
            )

            tool_calls_made.append(
                {
                    "name": fn_name,
                    "args": fn_args,
                    "result": result_str,
                    "server": server_name,
                }
            )

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "content": result_str,
                    "name": fn_name,
                }
            )

        # Check stop before follow-up Ollama call
        if app_state.stop_streaming:
            print("[MCP] Stop requested — skipping follow-up call")
            break

        # Ask Ollama again with tool results
        # think=False works around Ollama bug #10976 (think+tools=empty output)
        try:
            response = await run_in_thread(
                chat,
                model=app_state.selected_model,
                messages=messages,
                tools=filtered_tools,
                think=False,
            )
        except Exception as e:
            print(f"[MCP] Error in follow-up call: {e}")
            break

    # After tool loop completes, return None for pre_computed_response so the
    # caller falls through to the streaming path. The messages list now contains
    # the full tool exchange history, so the streaming call will produce the
    # final response with proper token-by-token delivery and thinking support.
    if tool_calls_made:
        print(
            f"[MCP] Tool loop complete after {rounds} round(s). Falling through to streaming."
        )

    return messages, tool_calls_made, None
