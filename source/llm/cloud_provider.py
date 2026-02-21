"""
Cloud LLM provider streaming integration.

Handles streaming responses from Anthropic (Claude), OpenAI, and Google Gemini
with real-time token broadcasting. Uses each SDK's native async streaming —
no background threads needed (unlike Ollama whose SDK is synchronous).

Same return signature as stream_ollama_chat for drop-in compatibility.
"""

import os
import base64
import json
from typing import List, Dict, Any, Optional

from ..core.connection import broadcast_message
from ..core.state import app_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_image_as_base64(path: str) -> Optional[str]:
    """Load an image file and return its base64-encoded content."""
    try:
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[Cloud] Failed to load image {path}: {e}")
        return None


def _guess_media_type(path: str) -> str:
    """Guess the MIME type from a file extension."""
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


# ---------------------------------------------------------------------------
# Anthropic (Claude) — native async streaming
# ---------------------------------------------------------------------------


def _build_anthropic_messages(
    chat_history: List[Dict[str, Any]],
    user_query: str,
    image_paths: List[str],
) -> List[Dict[str, Any]]:
    """Convert chat history to Anthropic message format."""
    messages = []

    for msg in chat_history:
        role = msg["role"]
        content = msg["content"]

        if role == "tool":
            continue

        if role == "user" and msg.get("images"):
            blocks: list = []
            for img_path in msg["images"]:
                if os.path.exists(img_path):
                    b64 = _load_image_as_base64(img_path)
                    if b64:
                        blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": _guess_media_type(img_path),
                                    "data": b64,
                                },
                            }
                        )
            blocks.append({"type": "text", "text": content})
            messages.append({"role": "user", "content": blocks})
        else:
            messages.append({"role": role, "content": content})

    # Add current user message
    existing_images = [p for p in image_paths if os.path.exists(p)]
    if existing_images:
        blocks = []
        for img_path in existing_images:
            b64 = _load_image_as_base64(img_path)
            if b64:
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _guess_media_type(img_path),
                            "data": b64,
                        },
                    }
                )
        blocks.append({"type": "text", "text": user_query})
        messages.append({"role": "user", "content": blocks})
    else:
        messages.append({"role": "user", "content": user_query})

    return messages


async def _stream_anthropic(
    api_key: str,
    model: str,
    user_query: str,
    image_paths: List[str],
    chat_history: List[Dict[str, Any]],
    tools: Optional[List[Dict]] = None,
    system_prompt: str = "",
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """Stream a response from Anthropic's Claude API using native async streaming."""
    import anthropic

    messages = _build_anthropic_messages(chat_history, user_query, image_paths)
    tool_calls_list: List[Dict[str, Any]] = []
    accumulated: list[str] = []
    thinking_tokens: list[str] = []
    token_stats: Dict[str, int] = {"prompt_eval_count": 0, "eval_count": 0}

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        if app_state.stop_streaming:
            return "", token_stats, tool_calls_list

        create_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": 16384,
            "messages": messages,
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        # Add thinking support for extended-thinking capable models
        is_thinking_model = any(kw in model for kw in ("opus", "sonnet"))
        if is_thinking_model:
            create_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": 10000,
            }

        if tools:
            create_kwargs["tools"] = tools

        async with client.messages.stream(**create_kwargs) as stream:
            async for event in stream:
                if app_state.stop_streaming:
                    break

                if event.type == "content_block_start":
                    block = event.content_block
                    if hasattr(block, "type"):
                        if block.type == "text" and thinking_tokens and not accumulated:
                            await broadcast_message("thinking_complete", "")

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "type"):
                        if delta.type == "thinking_delta":
                            thinking_tokens.append(delta.thinking)
                            await broadcast_message("thinking_chunk", delta.thinking)
                        elif delta.type == "text_delta":
                            if thinking_tokens and not accumulated:
                                await broadcast_message("thinking_complete", "")
                            accumulated.append(delta.text)
                            await broadcast_message("response_chunk", delta.text)

            # Get final message for token stats
            final_message = await stream.get_final_message()
            if final_message and hasattr(final_message, "usage"):
                usage = final_message.usage
                token_stats["prompt_eval_count"] = getattr(usage, "input_tokens", 0)
                token_stats["eval_count"] = getattr(usage, "output_tokens", 0)

        if thinking_tokens and not accumulated:
            await broadcast_message("thinking_complete", "")

        await broadcast_message("response_complete", "")
        await broadcast_message("token_usage", json.dumps(token_stats))

        return "".join(accumulated), token_stats, tool_calls_list

    except Exception as e:
        err = f"Error streaming from Anthropic: {e}"
        print(err)
        await broadcast_message("error", err)
        return err, {"prompt_eval_count": 0, "eval_count": 0}, tool_calls_list


# ---------------------------------------------------------------------------
# OpenAI — native async streaming
# ---------------------------------------------------------------------------


def _build_openai_messages(
    chat_history: List[Dict[str, Any]],
    user_query: str,
    image_paths: List[str],
) -> List[Dict[str, Any]]:
    """Convert chat history to OpenAI message format."""
    messages = []

    for msg in chat_history:
        role = msg["role"]
        content = msg["content"]

        if role == "tool":
            continue

        if role == "user" and msg.get("images"):
            parts: list = []
            for img_path in msg["images"]:
                if os.path.exists(img_path):
                    b64 = _load_image_as_base64(img_path)
                    if b64:
                        media_type = _guess_media_type(img_path)
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{b64}",
                                },
                            }
                        )
            parts.append({"type": "text", "text": content})
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": role, "content": content})

    # Current user message
    existing_images = [p for p in image_paths if os.path.exists(p)]
    if existing_images:
        parts = []
        for img_path in existing_images:
            b64 = _load_image_as_base64(img_path)
            if b64:
                media_type = _guess_media_type(img_path)
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}",
                        },
                    }
                )
        parts.append({"type": "text", "text": user_query})
        messages.append({"role": "user", "content": parts})
    else:
        messages.append({"role": "user", "content": user_query})

    return messages


async def _stream_openai(
    api_key: str,
    model: str,
    user_query: str,
    image_paths: List[str],
    chat_history: List[Dict[str, Any]],
    tools: Optional[List[Dict]] = None,
    system_prompt: str = "",
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """Stream a response from OpenAI's API using native async streaming."""
    from openai import AsyncOpenAI

    messages = _build_openai_messages(chat_history, user_query, image_paths)
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})
    tool_calls_list: List[Dict[str, Any]] = []
    accumulated: list[str] = []
    thinking_tokens: list[str] = []
    token_stats: Dict[str, int] = {"prompt_eval_count": 0, "eval_count": 0}

    try:
        client = AsyncOpenAI(api_key=api_key)

        if app_state.stop_streaming:
            return "", token_stats, tool_calls_list

        create_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            create_kwargs["tools"] = tools

        stream = await client.chat.completions.create(**create_kwargs)

        async for chunk in stream:
            if app_state.stop_streaming:
                break

            if not chunk.choices and hasattr(chunk, "usage") and chunk.usage:
                # Final chunk with usage stats
                token_stats["prompt_eval_count"] = chunk.usage.prompt_tokens or 0
                token_stats["eval_count"] = chunk.usage.completion_tokens or 0
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Handle reasoning/thinking content (o1, o3 models)
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                thinking_tokens.append(reasoning)
                await broadcast_message("thinking_chunk", reasoning)

            # Handle regular content
            if delta.content:
                if thinking_tokens and not accumulated:
                    await broadcast_message("thinking_complete", "")
                accumulated.append(delta.content)
                await broadcast_message("response_chunk", delta.content)

        if thinking_tokens and not accumulated:
            await broadcast_message("thinking_complete", "")

        await broadcast_message("response_complete", "")
        await broadcast_message("token_usage", json.dumps(token_stats))

        return "".join(accumulated), token_stats, tool_calls_list

    except Exception as e:
        err = f"Error streaming from OpenAI: {e}"
        print(err)
        await broadcast_message("error", err)
        return err, {"prompt_eval_count": 0, "eval_count": 0}, tool_calls_list


# ---------------------------------------------------------------------------
# Gemini — native async streaming
# ---------------------------------------------------------------------------


def _build_gemini_contents(
    chat_history: List[Dict[str, Any]],
    user_query: str,
    image_paths: List[str],
) -> list:
    """Convert chat history to Gemini content format."""
    from google.genai import types

    contents = []

    for msg in chat_history:
        role = msg["role"]
        content = msg["content"]

        if role == "tool":
            continue

        # Gemini uses "user" and "model" roles
        gemini_role = "model" if role == "assistant" else "user"

        if role == "user" and msg.get("images"):
            parts = []
            for img_path in msg["images"]:
                if os.path.exists(img_path):
                    b64 = _load_image_as_base64(img_path)
                    if b64:
                        media_type = _guess_media_type(img_path)
                        parts.append(
                            types.Part.from_bytes(
                                data=base64.standard_b64decode(b64),
                                mime_type=media_type,
                            )
                        )
            parts.append(types.Part.from_text(text=content))
            contents.append(types.Content(role=gemini_role, parts=parts))
        else:
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part.from_text(text=content)],
                )
            )

    # Current user message
    existing_images = [p for p in image_paths if os.path.exists(p)]
    if existing_images:
        parts = []
        for img_path in existing_images:
            b64 = _load_image_as_base64(img_path)
            if b64:
                media_type = _guess_media_type(img_path)
                parts.append(
                    types.Part.from_bytes(
                        data=base64.standard_b64decode(b64),
                        mime_type=media_type,
                    )
                )
        parts.append(types.Part.from_text(text=user_query))
        contents.append(types.Content(role="user", parts=parts))
    else:
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_query)],
            )
        )

    return contents


async def _stream_gemini(
    api_key: str,
    model: str,
    user_query: str,
    image_paths: List[str],
    chat_history: List[Dict[str, Any]],
    tools: Optional[List[Dict]] = None,
    system_prompt: str = "",
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """Stream a response from Google's Gemini API using native async streaming."""
    from google import genai
    from google.genai import types

    contents = _build_gemini_contents(chat_history, user_query, image_paths)
    tool_calls_list: List[Dict[str, Any]] = []
    accumulated: list[str] = []
    thinking_tokens: list[str] = []
    token_stats: Dict[str, int] = {"prompt_eval_count": 0, "eval_count": 0}

    try:
        client = genai.Client(api_key=api_key)

        if app_state.stop_streaming:
            return "", token_stats, tool_calls_list

        config_kwargs: Dict[str, Any] = {}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        # Enable thinking for capable models
        is_thinking_model = "thinking" in model or "2.5" in model
        if is_thinking_model:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=10000,
            )

        if tools:
            config_kwargs["tools"] = tools

        generate_config = (
            types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        )

        # Use the async API for streaming
        async for chunk in await client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_config,
        ):
            if app_state.stop_streaming:
                break

            if not chunk.candidates:
                # Check for usage metadata
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    um = chunk.usage_metadata
                    token_stats["prompt_eval_count"] = (
                        getattr(um, "prompt_token_count", 0) or 0
                    )
                    token_stats["eval_count"] = (
                        getattr(um, "candidates_token_count", 0) or 0
                    )
                continue

            candidate = chunk.candidates[0]
            if not candidate.content or not candidate.content.parts:
                continue

            for part in candidate.content.parts:
                # Handle thinking parts
                if hasattr(part, "thought") and part.thought:
                    thinking_tokens.append(part.text)
                    await broadcast_message("thinking_chunk", part.text)
                elif hasattr(part, "text") and part.text:
                    if thinking_tokens and not accumulated:
                        await broadcast_message("thinking_complete", "")
                    accumulated.append(part.text)
                    await broadcast_message("response_chunk", part.text)

            # Check usage metadata on each chunk
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                um = chunk.usage_metadata
                token_stats["prompt_eval_count"] = (
                    getattr(um, "prompt_token_count", 0) or 0
                )
                token_stats["eval_count"] = (
                    getattr(um, "candidates_token_count", 0) or 0
                )

        if thinking_tokens and not accumulated:
            await broadcast_message("thinking_complete", "")

        await broadcast_message("response_complete", "")
        await broadcast_message("token_usage", json.dumps(token_stats))

        return "".join(accumulated), token_stats, tool_calls_list

    except Exception as e:
        err = f"Error streaming from Gemini: {e}"
        print(err)
        await broadcast_message("error", err)
        return err, {"prompt_eval_count": 0, "eval_count": 0}, tool_calls_list


# ---------------------------------------------------------------------------
# Public API — called by the router
# ---------------------------------------------------------------------------


async def stream_cloud_chat(
    provider: str,
    model: str,
    api_key: str,
    user_query: str,
    image_paths: List[str],
    chat_history: List[Dict[str, Any]],
    tools: Optional[List[Dict]] = None,
    system_prompt: str = "",
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """
    Stream a response from a cloud LLM provider.

    Same return signature as stream_ollama_chat:
        (response_text, token_stats, tool_calls_list)

    Uses each provider's native async streaming — no background threads needed.
    """
    if provider == "anthropic":
        return await _stream_anthropic(
            api_key, model, user_query, image_paths, chat_history, tools, system_prompt
        )
    elif provider == "openai":
        return await _stream_openai(
            api_key, model, user_query, image_paths, chat_history, tools, system_prompt
        )
    elif provider == "gemini":
        return await _stream_gemini(
            api_key, model, user_query, image_paths, chat_history, tools, system_prompt
        )
    else:
        raise ValueError(f"Unknown cloud provider: {provider}")
