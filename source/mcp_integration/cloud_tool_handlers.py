"""
Cloud provider MCP tool call handlers.

Handles tool calling for Anthropic, OpenAI, and Gemini APIs.
Same loop logic as handle_mcp_tool_calls but uses cloud APIs instead of Ollama.
"""

import json
from typing import List, Dict, Any, Optional

from .manager import mcp_manager
from .retriever import retriever
from ..core.connection import broadcast_message
from ..core.thread_pool import run_in_thread
from ..config import MAX_MCP_TOOL_ROUNDS
from .terminal_executor import is_terminal_tool, execute_terminal_tool


async def handle_cloud_tool_calls(
    provider: str,
    model: str,
    api_key: str,
    messages: List[Dict[str, Any]],
    image_paths: List[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Check for and execute MCP tool calls from cloud providers.

    Same return signature as handle_mcp_tool_calls:
        (updated_messages, tool_calls_made, pre_computed_response)
        pre_computed_response is always None (caller streams the final response).

    Args:
        provider: "anthropic", "openai", or "gemini"
        model: The model name (without provider prefix)
        api_key: Decrypted API key
        messages: Conversation message history (in native chat_history format)
        image_paths: Image file paths
    """
    tool_calls_made: List[Dict[str, Any]] = []

    if not mcp_manager.has_tools():
        return messages, tool_calls_made, None

    # Skip tool detection if images are present (same as Ollama handler)
    has_images = any(msg.get("images") for msg in messages) or bool(image_paths)
    if has_images:
        return messages, tool_calls_made, None

    # Retrieve relevant tools logic
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

    # Use Ollama tools format for retrieval as it's the standard for the retriever
    all_ollama_tools = mcp_manager.get_ollama_tools() or []

    filtered_ollama_tools = retriever.retrieve_tools(
        query=user_query, all_tools=all_ollama_tools, always_on=always_on, top_k=top_k
    )

    allowed_tool_names = {t["function"]["name"] for t in filtered_ollama_tools}

    if len(filtered_ollama_tools) < len(all_ollama_tools):
        print(
            f"[MCP] Retriever selected {len(filtered_ollama_tools)}/{len(all_ollama_tools)} tools for query: '{user_query[:30]}...'"
        )

    if provider == "anthropic":
        return await _handle_anthropic_tools(
            model, api_key, messages, tool_calls_made, allowed_tool_names
        )
    elif provider == "openai":
        return await _handle_openai_tools(
            model, api_key, messages, tool_calls_made, allowed_tool_names
        )
    elif provider == "gemini":
        return await _handle_gemini_tools(
            model, api_key, messages, tool_calls_made, allowed_tool_names
        )

    return messages, tool_calls_made, None


# ---------------------------------------------------------------------------
# Anthropic tool handling
# ---------------------------------------------------------------------------


async def _handle_anthropic_tools(
    model: str,
    api_key: str,
    messages: List[Dict[str, Any]],
    tool_calls_made: List[Dict[str, Any]],
    allowed_tool_names: set[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Handle MCP tool calls via Anthropic Claude API."""
    import anthropic

    all_tools = mcp_manager.get_anthropic_tools()
    if not all_tools:
        return messages, tool_calls_made, None

    tools = [t for t in all_tools if t["name"] in allowed_tool_names]
    if not tools:
        return messages, tool_calls_made, None

    client = anthropic.Anthropic(api_key=api_key)

    # Convert messages to Anthropic format for tool detection
    anthropic_msgs = _to_anthropic_messages(messages)

    try:
        response = await run_in_thread(
            client.messages.create,
            model=model,
            max_tokens=4096,
            messages=anthropic_msgs,
            tools=tools,
        )
    except Exception as e:
        print(f"[MCP/Anthropic] Tool detection failed: {e}")
        return messages, tool_calls_made, None

    # Check if the response contains tool_use blocks
    has_tool_use = any(
        getattr(block, "type", None) == "tool_use" for block in (response.content or [])
    )
    if not has_tool_use:
        return messages, tool_calls_made, None

    # Tool loop
    rounds = 0
    while has_tool_use and rounds < MAX_MCP_TOOL_ROUNDS:
        rounds += 1

        # Add assistant response to messages
        anthropic_msgs.append({"role": "assistant", "content": response.content})

        # Process each tool_use block
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            fn_name = block.name
            fn_args = block.input or {}
            tool_use_id = block.id
            server_name = mcp_manager.get_tool_server_name(fn_name)

            print(
                f"[MCP/Anthropic] Tool call: {fn_name}({fn_args}) from '{server_name}'"
            )

            # Terminal tool interception — same approval/PTY/streaming as Ollama
            if is_terminal_tool(fn_name, server_name):
                result = await execute_terminal_tool(fn_name, fn_args, server_name)
            else:
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

                try:
                    result = await mcp_manager.call_tool(fn_name, dict(fn_args))
                except Exception as e:
                    result = f"Error executing tool: {e}"

            result_str = _truncate_result(result)

            if not is_terminal_tool(fn_name, server_name):
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

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_str,
                }
            )

        # Send tool results back
        anthropic_msgs.append({"role": "user", "content": tool_results})

        try:
            response = await run_in_thread(
                client.messages.create,
                model=model,
                max_tokens=4096,
                messages=anthropic_msgs,
                tools=tools,
            )
        except Exception as e:
            print(f"[MCP/Anthropic] Follow-up call failed: {e}")
            break

        has_tool_use = any(
            getattr(block, "type", None) == "tool_use"
            for block in (response.content or [])
        )

    if tool_calls_made:
        print(f"[MCP/Anthropic] Tool loop complete after {rounds} round(s)")

    # Update the original messages with tool exchange for context,
    # but let the streaming path handle the final response
    return messages, tool_calls_made, None


def _to_anthropic_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert internal chat history format to Anthropic messages."""
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool":
            continue
        result.append({"role": role, "content": msg.get("content", "")})
    return result


# ---------------------------------------------------------------------------
# OpenAI tool handling
# ---------------------------------------------------------------------------


async def _handle_openai_tools(
    model: str,
    api_key: str,
    messages: List[Dict[str, Any]],
    tool_calls_made: List[Dict[str, Any]],
    allowed_tool_names: set[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Handle MCP tool calls via OpenAI API."""
    import openai

    all_tools = mcp_manager.get_openai_tools()
    if not all_tools:
        return messages, tool_calls_made, None

    tools = [t for t in all_tools if t["function"]["name"] in allowed_tool_names]
    if not tools:
        return messages, tool_calls_made, None

    client = openai.OpenAI(api_key=api_key)

    openai_msgs = _to_openai_messages(messages)

    try:
        response = await run_in_thread(
            client.chat.completions.create,
            model=model,
            messages=openai_msgs,
            tools=tools,
        )
    except Exception as e:
        print(f"[MCP/OpenAI] Tool detection failed: {e}")
        return messages, tool_calls_made, None

    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message.tool_calls:
        return messages, tool_calls_made, None

    # Tool loop
    rounds = 0
    while choice and choice.message.tool_calls and rounds < MAX_MCP_TOOL_ROUNDS:
        rounds += 1

        # Add assistant message with tool calls
        openai_msgs.append(choice.message.model_dump())

        for tc in choice.message.tool_calls:
            fn_name = tc.function.name
            fn_args_str = tc.function.arguments
            try:
                fn_args = json.loads(fn_args_str) if fn_args_str else {}
            except json.JSONDecodeError:
                fn_args = {}

            server_name = mcp_manager.get_tool_server_name(fn_name)

            print(f"[MCP/OpenAI] Tool call: {fn_name}({fn_args}) from '{server_name}'")

            # Terminal tool interception
            if is_terminal_tool(fn_name, server_name):
                result = await execute_terminal_tool(fn_name, fn_args, server_name)
            else:
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

                try:
                    result = await mcp_manager.call_tool(fn_name, dict(fn_args))
                except Exception as e:
                    result = f"Error executing tool: {e}"

            result_str = _truncate_result(result)

            if not is_terminal_tool(fn_name, server_name):
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

            # Add tool result message
            openai_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                }
            )

        try:
            response = await run_in_thread(
                client.chat.completions.create,
                model=model,
                messages=openai_msgs,
                tools=tools,
            )
            choice = response.choices[0] if response.choices else None
        except Exception as e:
            print(f"[MCP/OpenAI] Follow-up call failed: {e}")
            break

    if tool_calls_made:
        print(f"[MCP/OpenAI] Tool loop complete after {rounds} round(s)")

    return messages, tool_calls_made, None


def _to_openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert internal chat history format to OpenAI messages."""
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool":
            continue
        result.append({"role": role, "content": msg.get("content", "")})
    return result


# ---------------------------------------------------------------------------
# Gemini tool handling
# ---------------------------------------------------------------------------


async def _handle_gemini_tools(
    model: str,
    api_key: str,
    messages: List[Dict[str, Any]],
    tool_calls_made: List[Dict[str, Any]],
    allowed_tool_names: set[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Handle MCP tool calls via Gemini API."""
    from google import genai
    from google.genai import types

    gemini_tools_list = mcp_manager.get_gemini_tools()
    if not gemini_tools_list:
        return messages, tool_calls_made, None

    # Filter tools based on allowed names
    filtered_declarations = []
    for tool in gemini_tools_list:
        if hasattr(tool, "function_declarations") and tool.function_declarations:
            for fd in tool.function_declarations:
                if fd.name in allowed_tool_names:
                    filtered_declarations.append(fd)

    if not filtered_declarations:
        return messages, tool_calls_made, None

    tools = [types.Tool(function_declarations=filtered_declarations)]

    client = genai.Client(api_key=api_key)

    # Build Gemini contents from messages
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(tools=tools)

    try:
        response = await run_in_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )
    except Exception as e:
        print(f"[MCP/Gemini] Tool detection failed: {e}")
        return messages, tool_calls_made, None

    # Check for function calls in response
    fn_calls = _extract_gemini_function_calls(response)
    if not fn_calls:
        return messages, tool_calls_made, None

    # Tool loop
    rounds = 0
    while fn_calls and rounds < MAX_MCP_TOOL_ROUNDS:
        rounds += 1

        # Add model response to contents
        if response.candidates and response.candidates[0].content:
            contents.append(response.candidates[0].content)

        # Process each function call
        fn_response_parts = []
        for fc in fn_calls:
            fn_name = fc["name"]
            fn_args = fc["args"]
            server_name = mcp_manager.get_tool_server_name(fn_name)

            print(f"[MCP/Gemini] Tool call: {fn_name}({fn_args}) from '{server_name}'")

            # Terminal tool interception
            if is_terminal_tool(fn_name, server_name):
                result = await execute_terminal_tool(fn_name, fn_args, server_name)
            else:
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

                try:
                    result = await mcp_manager.call_tool(fn_name, dict(fn_args))
                except Exception as e:
                    result = f"Error executing tool: {e}"

            result_str = _truncate_result(result)

            if not is_terminal_tool(fn_name, server_name):
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

            fn_response_parts.append(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": result_str},
                )
            )

        # Add function response
        contents.append(types.Content(role="user", parts=fn_response_parts))

        try:
            response = await run_in_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            print(f"[MCP/Gemini] Follow-up call failed: {e}")
            break

        fn_calls = _extract_gemini_function_calls(response)

    if tool_calls_made:
        print(f"[MCP/Gemini] Tool loop complete after {rounds} round(s)")

    return messages, tool_calls_made, None


def _to_gemini_contents(messages: List[Dict[str, Any]]) -> list:
    """Convert internal chat history format to Gemini contents."""
    from google.genai import types

    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool":
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=msg.get("content", ""))],
            )
        )
    return contents


def _extract_gemini_function_calls(response) -> List[Dict[str, Any]]:
    """Extract function calls from a Gemini response."""
    fn_calls = []
    if not response.candidates:
        return fn_calls

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        return fn_calls

    for part in candidate.content.parts:
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            fn_calls.append(
                {
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                }
            )

    return fn_calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_result(result: str) -> str:
    """Truncate tool result if excessively large."""
    result_str = str(result)
    if len(result_str) > 100000:
        print(f"[MCP] Truncating large tool output ({len(result_str)} chars)")
        return result_str[:100000] + "... [Output truncated due to length]"
    return result_str
