"""
HTTP REST API endpoints.

Use for:
- One-time data fetches (models list)
- Settings management (enabled models, API keys)
- Health checks
- Cloud provider model listing
"""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import ollama


router = APIRouter(prefix="/api")


# ============================================
# Health Check
# ============================================


@router.get("/health")
async def health_check():
    """Check if the server is running."""
    return {"status": "healthy"}


# ============================================
# Models API
# ============================================


class OllamaModel(BaseModel):
    """Represents an Ollama model."""

    name: str
    size: int  # in bytes
    parameter_size: str
    quantization: str


@router.get("/models/ollama")
async def get_ollama_models() -> List[dict]:
    """
    Get all Ollama models installed on the user's machine.

    Calls `ollama.list()` which talks to the local Ollama daemon
    and returns every model that has been pulled.
    """
    try:
        # Run synchronous ollama.list() in a thread to avoid blocking
        response = await asyncio.to_thread(ollama.list)
        models = []
        # The Ollama SDK returns objects with attributes, not dicts.
        # e.g. Model(model='gemma3:12b', size=..., details=ModelDetails(...))
        for m in response.models:
            details = m.details
            models.append(
                {
                    "name": m.model or "unknown",
                    "size": m.size or 0,
                    "parameter_size": getattr(details, "parameter_size", "")
                    if details
                    else "",
                    "quantization": getattr(details, "quantization_level", "")
                    if details
                    else "",
                }
            )
        return models
    except Exception as e:
        print(f"[HTTP] Error fetching Ollama models: {e}")
        return []


# ============================================
# Enabled Models API (persisted in DB)
# ============================================


class EnabledModelsUpdate(BaseModel):
    """Request body for toggling models."""

    models: List[str]


@router.get("/models/enabled")
async def get_enabled_models() -> List[str]:
    """
    Get the list of model names the user has toggled on.

    These are stored in the SQLite database so they persist across restarts.
    """
    from ..database import db

    return db.get_enabled_models()


@router.put("/models/enabled")
async def set_enabled_models(body: EnabledModelsUpdate):
    """
    Replace the full list of enabled models with the given list.

    Called every time the user toggles a model on/off in SettingsModels.
    """
    from ..database import db

    db.set_enabled_models(body.models)
    return {"status": "updated", "models": body.models}


# ============================================
# API Key Management
# ============================================


class ApiKeyUpdate(BaseModel):
    """Request body for saving an API key."""

    key: str


@router.get("/keys")
async def get_api_key_status():
    """
    Get status of all provider API keys.
    Returns which providers have keys stored and their masked values.
    """
    from ..llm.key_manager import key_manager

    return key_manager.get_api_key_status()


@router.put("/keys/{provider}")
async def save_api_key(provider: str, body: ApiKeyUpdate):
    """
    Validate and store an API key for a provider.

    Performs a lightweight validation call before storing.
    Uses async clients/threads to avoid blocking the server loop.
    """
    from ..llm.key_manager import key_manager, VALID_PROVIDERS

    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    api_key = body.key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Validate the key by making a lightweight API call
    try:
        if provider == "anthropic":
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=api_key)
            # Count message tokens as a lightweight validation
            await client.messages.count_tokens(
                model="claude-3-haiku-20240307",  # Use a cheap/fast model for validation
                messages=[{"role": "user", "content": "hi"}],
            )

        elif provider == "openai":
            import openai

            client = openai.AsyncOpenAI(api_key=api_key)
            # List models as a lightweight validation
            await client.models.list()

        elif provider == "gemini":
            from google import genai

            client = genai.Client(api_key=api_key)
            # List models as a lightweight validation (run in thread)
            await asyncio.to_thread(
                lambda: list(client.models.list(config={"page_size": 1}))
            )

    except Exception as e:
        error_msg = str(e)
        print(f"[HTTP] API key validation failed for {provider}: {error_msg}")
        raise HTTPException(
            status_code=401, detail=f"Invalid API key: {error_msg[:200]}"
        )

    # Key is valid — encrypt and store
    key_manager.save_api_key(provider, api_key)
    return {
        "status": "saved",
        "provider": provider,
        "masked": key_manager.mask_key(api_key),
    }


@router.delete("/keys/{provider}")
async def delete_api_key(provider: str):
    """Remove a stored API key for a provider."""
    from ..llm.key_manager import key_manager, VALID_PROVIDERS

    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    key_manager.delete_api_key(provider)

    # Also remove any cloud models from the enabled list that belong to this provider
    from ..database import db

    enabled = db.get_enabled_models()
    filtered = [m for m in enabled if not m.startswith(f"{provider}/")]
    if len(filtered) != len(enabled):
        db.set_enabled_models(filtered)

    return {"status": "deleted", "provider": provider}


# ============================================
# Cloud Provider Models
# ============================================

# Fallback lists in case APIs fail
ANTHROPIC_FALLBACK = [
    {
        "name": "claude-3-7-sonnet-20250219",
        "description": "Claude 3.7 Sonnet — latest hybrid reasoning",
    },
    {
        "name": "claude-3-5-sonnet-20241022",
        "description": "Claude 3.5 Sonnet — high intelligence",
    },
    {
        "name": "claude-3-5-haiku-20241022",
        "description": "Claude 3.5 Haiku — fastest",
    },
    {"name": "claude-3-opus-20240229", "description": "Claude 3 Opus — powerful"},
]

OPENAI_FALLBACK = [
    {"name": "o3-mini", "description": "o3-mini — latest fast reasoning"},
    {"name": "o1", "description": "o1 — high-reasoning flagship"},
    {"name": "gpt-4o", "description": "GPT-4o — versatile flagship"},
    {"name": "gpt-4o-mini", "description": "GPT-4o Mini — fast & cheap"},
    {"name": "o1-mini", "description": "o1-mini — efficient reasoning"},
]

GEMINI_FALLBACK = [
    {"name": "gemini-2.0-flash", "description": "Gemini 2.0 Flash — next-gen speed"},
    {
        "name": "gemini-2.0-pro-exp-0505",
        "description": "Gemini 2.0 Pro (Exp) — highest intelligence",
    },
    {"name": "gemini-1.5-pro", "description": "Gemini 1.5 Pro — balanced"},
    {"name": "gemini-1.5-flash", "description": "Gemini 1.5 Flash — fast"},
]


OPENAI_FALLBACK = [
    {"name": "gpt-4o", "description": "GPT-4o — versatile & fast"},
    {"name": "gpt-4o-mini", "description": "GPT-4o Mini — cost-efficient"},
    {"name": "o1-preview", "description": "o1 Preview — advanced reasoning"},
    {"name": "o1-mini", "description": "o1 Mini — fast reasoning"},
    {"name": "gpt-4-turbo", "description": "GPT-4 Turbo — capable"},
]

GEMINI_FALLBACK = [
    {
        "name": "gemini-2.0-flash-exp",
        "description": "Gemini 2.0 Flash (Exp) — next gen",
    },
    {"name": "gemini-1.5-pro", "description": "Gemini 1.5 Pro — balanced"},
    {"name": "gemini-1.5-flash", "description": "Gemini 1.5 Flash — fast"},
    {
        "name": "gemini-1.5-flash-8b",
        "description": "Gemini 1.5 Flash-8B — extremely fast",
    },
]


@router.get("/models/anthropic")
async def get_anthropic_models() -> List[dict]:
    """Get available Anthropic models. Requires a stored API key."""
    from ..llm.key_manager import key_manager

    api_key = key_manager.get_api_key("anthropic")
    if not api_key:
        return []

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)

        models = []
        async for m in client.models.list(limit=100):
            # Use display_name if available, else ID
            display = getattr(m, "display_name", m.id)
            models.append(
                {
                    "name": f"anthropic/{m.id}",
                    "provider": "anthropic",
                    "description": display,
                }
            )

        # If we got models, return them
        if models:
            # Sort by creation date if available (descending), else name
            models.sort(key=lambda x: x["name"], reverse=True)
            return models

    except Exception as e:
        print(f"[HTTP] Error fetching Anthropic models via API: {e}")
        # Fall through to fallback

    # Fallback
    return [
        {
            "name": f"anthropic/{m['name']}",
            "provider": "anthropic",
            "description": m["description"],
        }
        for m in ANTHROPIC_FALLBACK
    ]


@router.get("/models/openai")
async def get_openai_models() -> List[dict]:
    """Get available OpenAI models. Requires a stored API key."""
    from ..llm.key_manager import key_manager

    api_key = key_manager.get_api_key("openai")
    if not api_key:
        return []

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.models.list()

        # Filter to chat-capable models (gpt-*, o1*, o3*, o4*, chatgpt-*)
        chat_prefixes = ("gpt-4", "gpt-3.5", "o1", "o3", "o4", "chatgpt-")
        exclude_keywords = (
            "instruct",
            "realtime",
            "audio",
            "search",
            "tts",
            "whisper",
            "dall-e",
            "embedding",
            "moderation",
            "davinci",
            "babbage",
        )

        models = []
        for m in response.data:
            model_id = m.id
            # Simple check: starts with a known prefix AND doesn't contain excluded keywords
            if any(model_id.startswith(p) for p in chat_prefixes):
                if not any(kw in model_id for kw in exclude_keywords):
                    models.append(
                        {
                            "name": f"openai/{model_id}",
                            "provider": "openai",
                            "description": model_id,
                        }
                    )

        # Sort alphabetically
        models.sort(key=lambda x: x["name"])
        if models:
            return models

    except Exception as e:
        print(f"[HTTP] Error fetching OpenAI models: {e}")
        # Fall through to fallback

    # Fallback
    return [
        {
            "name": f"openai/{m['name']}",
            "provider": "openai",
            "description": m["description"],
        }
        for m in OPENAI_FALLBACK
    ]


@router.get("/models/gemini")
async def get_gemini_models() -> List[dict]:
    """Get available Gemini models. Requires a stored API key."""
    from ..llm.key_manager import key_manager

    api_key = key_manager.get_api_key("gemini")
    if not api_key:
        return []

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Run sync list_models in thread
        # Note: The Google GenAI SDK might return an iterator or list depending on version
        response = await asyncio.to_thread(lambda: list(client.models.list()))

        models = []
        for m in response:
            model_name = m.name or ""
            # Only include generateContent-capable models
            actions = m.supported_actions or []
            if "generateContent" not in actions:
                continue
            # Strip "models/" prefix if present
            if model_name.startswith("models/"):
                model_name = model_name[7:]
            # Skip embedding/vision-only/legacy models
            if any(kw in model_name for kw in ("embedding", "aqa", "bison", "gecko")):
                continue
            display_name = m.display_name or model_name
            models.append(
                {
                    "name": f"gemini/{model_name}",
                    "provider": "gemini",
                    "description": display_name,
                }
            )

        models.sort(key=lambda x: x["name"])
        if models:
            return models

    except Exception as e:
        print(f"[HTTP] Error fetching Gemini models: {e}")
        # Fall through to fallback

    # Fallback
    return [
        {
            "name": f"gemini/{m['name']}",
            "provider": "gemini",
            "description": m["description"],
        }
        for m in GEMINI_FALLBACK
    ]
