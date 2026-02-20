"""
LLM Provider Router.

Routes chat requests to the correct provider (Ollama or cloud) based on the
model name prefix. Cloud models use the format "provider/model-name" (e.g.,
"anthropic/claude-sonnet-4-20250514"). Ollama models have no prefix.
"""

from typing import List, Dict, Any, Tuple


def parse_provider(model_name: str) -> Tuple[str, str]:
    """
    Parse a model name into (provider, model).

    Examples:
        "anthropic/claude-sonnet-4-20250514" -> ("anthropic", "claude-sonnet-4-20250514")
        "openai/gpt-4o" -> ("openai", "gpt-4o")
        "gemini/gemini-2.5-pro" -> ("gemini", "gemini-2.5-pro")
        "qwen3-vl:8b-instruct" -> ("ollama", "qwen3-vl:8b-instruct")
    """
    if "/" in model_name:
        provider, _, model = model_name.partition("/")
        if provider in ("anthropic", "openai", "gemini"):
            return provider, model
    return "ollama", model_name


async def route_chat(
    model_name: str,
    user_query: str,
    image_paths: List[str],
    chat_history: List[Dict[str, Any]],
    forced_skills: List[Dict[str, Any]] | None = None,
) -> tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """
    Route a chat request to the correct LLM provider.

    Same return signature as stream_ollama_chat:
        (response_text, token_stats, tool_calls_list)

    For Ollama models, delegates to stream_ollama_chat.
    For cloud models, handles MCP tool detection, then streams via cloud_provider.
    """
    provider, model = parse_provider(model_name)

    from ..database import db
    from .prompt import build_system_prompt
    from ..mcp_integration.skill_injector import get_skills_to_inject, build_skills_prompt_block
    from ..mcp_integration.manager import mcp_manager

    # Build skills block for system prompt
    # For now, pass empty retrieved_tools — auto-detection happens based on
    # whatever tools the retriever selects. We'll pass the actual filtered
    # tools once available, but forced_skills from slash commands work immediately.
    skills_to_inject = get_skills_to_inject(
        retrieved_tools=[],
        forced_skills=forced_skills or [],
        db=db,
        mcp_manager=mcp_manager,
    )
    skills_block = build_skills_prompt_block(skills_to_inject)

    if skills_to_inject:
        print(f"[Skills] Injecting {len(skills_to_inject)} skill(s): {[s['skill_name'] for s in skills_to_inject]}")

    custom_template = db.get_setting("system_prompt_template")
    system_prompt = build_system_prompt(skills_block=skills_block, template=custom_template)

    if provider == "ollama":
        # Use existing Ollama pipeline (MCP tool handling is built-in)
        from .ollama_provider import stream_ollama_chat

        return await stream_ollama_chat(user_query, image_paths, chat_history, system_prompt)

    # Cloud provider path
    from .key_manager import key_manager
    from .cloud_provider import stream_cloud_chat
    from ..mcp_integration.cloud_tool_handlers import handle_cloud_tool_calls
    from ..mcp_integration.manager import mcp_manager

    # Get API key
    api_key = key_manager.get_api_key(provider)
    if not api_key:
        from ..core.connection import broadcast_message

        await broadcast_message(
            "error", f"No API key configured for {provider}. Add one in Settings."
        )
        return (
            f"Error: No API key for {provider}",
            {"prompt_eval_count": 0, "eval_count": 0},
            [],
        )

    # MCP tool calling phase (runs before streaming)
    tool_calls_list: List[Dict[str, Any]] = []
    if mcp_manager.has_tools():
        try:
            messages_for_tools = [
                {"role": m["role"], "content": m["content"]} for m in chat_history
            ]
            messages_for_tools.append({"role": "user", "content": user_query})

            _, tool_calls_list, _ = await handle_cloud_tool_calls(
                provider, model, api_key, messages_for_tools, image_paths
            )
        except Exception as e:
            print(f"[Router] Cloud tool calling phase failed: {e}")

    # Build updated chat history with tool exchange for context
    updated_history = list(chat_history)
    if tool_calls_list:
        # Add tool results as context so the streaming call knows about them
        tool_summary = "\n".join(
            f"[Tool: {tc['name']}] Result: {tc['result'][:500]}"
            for tc in tool_calls_list
        )
        # Inject tool results as a system-level context message
        updated_history = list(chat_history)
        updated_history.append(
            {
                "role": "user",
                "content": f"[System: The following tool calls were executed to help answer the query]\n{tool_summary}\n\n[Original query: {user_query}]",
            }
        )
        # The streaming call uses the original user_query but with tool context
        response_text, token_stats, _ = await stream_cloud_chat(
            provider,
            model,
            api_key,
            f"Based on the tool results above, answer the original query: {user_query}",
            image_paths,
            updated_history,
            system_prompt=system_prompt,
        )
    else:
        # No tools needed — straight streaming
        response_text, token_stats, _ = await stream_cloud_chat(
            provider,
            model,
            api_key,
            user_query,
            image_paths,
            chat_history,
            system_prompt=system_prompt,
        )

    return response_text, token_stats, tool_calls_list
