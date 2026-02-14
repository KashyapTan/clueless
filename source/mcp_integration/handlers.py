"""
MCP tool call handlers.

Handles the execution of MCP tool calls from Ollama responses.
"""
import json
from typing import List, Dict, Any

from ollama import chat

from .manager import mcp_manager
from ..core.connection import broadcast_message
from ..core.state import app_state


async def handle_mcp_tool_calls(
    messages: List[Dict[str, Any]], 
    image_paths: List[str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Check for and execute MCP tool calls from Ollama.
    
    If Ollama wants to call MCP tools, this function:
    1. Makes the tool calls via MCP servers
    2. Broadcasts tool_call events to the UI so users see what happened
    3. Appends tool call + result messages to the conversation
    4. Repeats until Ollama stops requesting tools
    
    Args:
        messages: The conversation message history
        image_paths: List of image paths attached to the query
    
    Returns:
        (updated_messages, tool_calls_made)
        - updated_messages: the messages list with tool exchanges appended
        - tool_calls_made: list of {name, args, result, server} for UI display
    """
    tool_calls_made = []
    
    if not mcp_manager.has_tools():
        return messages, tool_calls_made
    
    # Only do tool detection for text-only queries (no images)
    # Vision models + tool calling don't always mix well
    has_images = any(msg.get('images') for msg in messages) or bool(image_paths)
    if has_images:
        return messages, tool_calls_made
    
    # Non-streamed call to detect tool requests
    try:
        response = chat(
            model=app_state.selected_model,
            messages=messages,
            tools=mcp_manager.get_ollama_tools(),
        )
    except Exception as e:
        print(f"[MCP] Error in tool detection call: {e}")
        return messages, tool_calls_made
    
    # Loop: keep calling tools until Ollama gives a final text answer
    from ..config import MAX_MCP_TOOL_ROUNDS
    rounds = 0
    
    while response.message.tool_calls and rounds < MAX_MCP_TOOL_ROUNDS:
        rounds += 1
        for tool_call in response.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments
            server_name = mcp_manager.get_tool_server_name(fn_name)
            
            print(f"[MCP] Tool call: {fn_name}({fn_args}) from server '{server_name}'")
            
            # Broadcast to UI so users see the tool being called
            await broadcast_message("tool_call", json.dumps({
                "name": fn_name,
                "args": fn_args,
                "server": server_name,
                "status": "calling"
            }))
            
            # Execute the tool via MCP
            try:
                result = await mcp_manager.call_tool(fn_name, fn_args)
            except Exception as e:
                result = f"Error executing tool: {e}"

            print(f"[MCP] Tool result:\n{result[0:100]}...")
            
            # Broadcast result to UI
            await broadcast_message("tool_call", json.dumps({
                "name": fn_name,
                "args": fn_args,
                "result": str(result),
                "server": server_name,
                "status": "complete"
            }))
            
            tool_calls_made.append({
                "name": fn_name,
                "args": fn_args,
                "result": str(result),
                "server": server_name,
            })
            
            # Add tool exchange to messages for context
            messages.append(response.message.model_dump())
            messages.append({
                "role": "tool",
                "content": str(result),
            })
        
        # Ask Ollama again with tool results
        try:
            response = chat(
                model=app_state.selected_model,
                messages=messages,
                tools=mcp_manager.get_ollama_tools(),
            )
        except Exception as e:
            print(f"[MCP] Error in follow-up call: {e}")
            break
    
    return messages, tool_calls_made
