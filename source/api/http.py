"""
HTTP REST API endpoints.

Use for:
- One-time data fetches (models list)
- Settings management (enabled models)
- Health checks
"""
from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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
        import ollama
        response = ollama.list()
        models = []
        # The Ollama SDK returns objects with attributes, not dicts.
        # e.g. Model(model='gemma3:12b', size=..., details=ModelDetails(...))
        for m in response.models:
            details = m.details
            models.append({
                "name": m.model or "unknown",
                "size": m.size or 0,
                "parameter_size": getattr(details, "parameter_size", "") if details else "",
                "quantization": getattr(details, "quantization_level", "") if details else "",
            })
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
