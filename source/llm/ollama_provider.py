"""
Ollama LLM streaming integration.

Handles streaming responses from Ollama with real-time token broadcasting.
"""
import os
import threading
import asyncio
import json
from typing import List, Dict, Any

from ollama import chat

from ..core.connection import broadcast_message
from ..core.state import app_state
from ..mcp_integration.handlers import handle_mcp_tool_calls
from ..mcp_integration.manager import mcp_manager


async def stream_ollama_chat(
    user_query: str, 
    image_paths: List[str], 
    chat_history: List[Dict[str, Any]]
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """
    Stream Ollama response without blocking the event loop.

    A background thread iterates the blocking Ollama generator and schedules
    WebSocket broadcasts for each incremental token. Returns a tuple of
    (full_output_text, token_stats_dict, tool_calls_list) once streaming completes.
    
    Args:
        user_query: The user's question
        image_paths: List of image file paths (can be empty for text-only)
        chat_history: Previous conversation messages
    
    Returns:
        Tuple of (response_text, token_stats, tool_calls)
    """
    loop = asyncio.get_running_loop()
    done_future: asyncio.Future[tuple[str, Dict[str, int], List[Dict[str, Any]]]] = loop.create_future()

    def safe_schedule(coro):
        try:
            loop.call_soon_threadsafe(asyncio.create_task, coro)
        except RuntimeError:
            pass

    def producer():
        accumulated: list[str] = []
        thinking_tokens: list[str] = []
        final_message_content: str | None = None
        collected_token_stats: Dict[str, int] = {"prompt_eval_count": 0, "eval_count": 0}
        
        # Build messages list from chat history
        messages = []
        for msg in chat_history:
            message_data = {
                'role': msg['role'],
                'content': msg['content'],
            }
            # Include images only if they still exist on disk
            if msg.get('images'):
                existing_images = [p for p in msg['images'] if os.path.exists(p)]
                if existing_images:
                    message_data['images'] = existing_images
            messages.append(message_data)
        
        # Add current user query
        existing_image_paths = [p for p in image_paths if os.path.exists(p)]
        if existing_image_paths:
            messages.append({
                'role': 'user',
                'content': user_query,
                'images': existing_image_paths,
            })
        else:
            messages.append({
                'role': 'user',
                'content': user_query,
            })
        
        # ── MCP Tool Calling Phase ─────────────────────────────────
        tool_calls_list = []
        if mcp_manager.has_tools():
            import concurrent.futures
            future = concurrent.futures.Future()
            
            async def _do_tool_calls():
                try:
                    updated, calls = await handle_mcp_tool_calls(messages.copy(), image_paths)
                    future.set_result((updated, calls))
                except Exception as e:
                    future.set_exception(e)
            
            try:
                loop.call_soon_threadsafe(asyncio.ensure_future, _do_tool_calls())
                updated_messages, tool_calls_list = future.result(timeout=90)
                messages = updated_messages
            except Exception as e:
                print(f"[MCP] Tool calling phase failed: {e}")
        
        try:
            generator = chat(
                model=app_state.selected_model,
                messages=messages,
                stream=True,
            )
            
            for idx, chunk in enumerate(generator):
                # Check if stop was requested
                if app_state.stop_streaming:
                    break
                
                content_token, thinking_token = _extract_token(chunk)
                
                # Handle thinking tokens
                if thinking_token:
                    thinking_tokens.append(thinking_token)
                    safe_schedule(broadcast_message("thinking_chunk", thinking_token))
                
                # Handle regular content
                if content_token:
                    if thinking_tokens and not accumulated:
                        safe_schedule(broadcast_message("thinking_complete", ""))
                    accumulated.append(content_token)
                    safe_schedule(broadcast_message("response_chunk", content_token))
                    
                # Track final message and token stats
                if hasattr(chunk, 'done') and getattr(chunk, 'done'):
                    token_stats = {
                        "prompt_eval_count": getattr(chunk, 'prompt_eval_count', 0),
                        "eval_count": getattr(chunk, 'eval_count', 0),
                    }
                    collected_token_stats["prompt_eval_count"] = token_stats["prompt_eval_count"] or 0
                    collected_token_stats["eval_count"] = token_stats["eval_count"] or 0
                    safe_schedule(broadcast_message("token_usage", json.dumps(token_stats)))
                    
                    if hasattr(chunk, 'message'):
                        msg = getattr(chunk, 'message')
                        if msg is not None and hasattr(msg, 'content'):
                            mc = getattr(msg, 'content')
                            if isinstance(mc, str) and mc:
                                final_message_content = mc
            
            # Handle edge cases
            if thinking_tokens and not accumulated:
                safe_schedule(broadcast_message("thinking_complete", ""))
            
            if not accumulated and final_message_content:
                accumulated.append(final_message_content)
                safe_schedule(broadcast_message("response_chunk", final_message_content))
            elif not accumulated and not app_state.stop_streaming:
                safe_schedule(broadcast_message("error", "No content tokens extracted from stream."))
            
            safe_schedule(broadcast_message("response_complete", ""))
            loop.call_soon_threadsafe(done_future.set_result, (''.join(accumulated), collected_token_stats, tool_calls_list))
            
        except Exception as e:
            err = f"Error streaming from Ollama: {e}"
            print(err)
            safe_schedule(broadcast_message("error", err))
            if not done_future.done():
                loop.call_soon_threadsafe(done_future.set_result, (err, collected_token_stats, tool_calls_list))

    threading.Thread(target=producer, daemon=True).start()
    return await done_future


def _extract_token(chunk) -> tuple[str | None, str | None]:
    """
    Extract content and thinking tokens from a streaming chunk.
    
    Supports both dict (older client) and object (dataclass) shapes.
    Returns (content_token, thinking_token).
    """
    content_token = None
    thinking_token = None
    
    # Dict-based chunk
    if isinstance(chunk, dict):
        msg = chunk.get('message')
        if isinstance(msg, dict):
            content_token = msg.get('content') if isinstance(msg.get('content'), str) and msg.get('content') else None
            thinking_token = msg.get('thinking') if isinstance(msg.get('thinking'), str) and msg.get('thinking') else None
        if not content_token:
            for key in ('response', 'content', 'delta', 'text', 'token'):
                tok = chunk.get(key)
                if isinstance(tok, str) and tok:
                    content_token = tok
                    break
        return (content_token, thinking_token)
    
    # Object-based chunk
    if hasattr(chunk, 'message'):
        msg = getattr(chunk, 'message')
        if msg is not None:
            if hasattr(msg, 'thinking'):
                val = getattr(msg, 'thinking')
                if isinstance(val, str) and val:
                    thinking_token = val
            if hasattr(msg, 'content'):
                val = getattr(msg, 'content')
                if isinstance(val, str) and val:
                    content_token = val
    
    # Fallback for content
    if not content_token:
        for attr in ('response', 'content', 'delta', 'token'):
            if hasattr(chunk, attr):
                val = getattr(chunk, attr)
                if isinstance(val, str) and val:
                    content_token = val
                    break
    
    return (content_token, thinking_token)
