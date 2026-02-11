"""
API routes for model configuration.
Supports ANY provider (OpenAI, Anthropic, Groq, Mistral, Gemini, Copilot, Local, etc.)
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, SecretStr, Field, field_validator
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.user_config import UserModelConfig, ProviderType, ConnectionStatus, ModelUsageLog
from backend.services.model_provider import ModelService
from backend.core.security import encrypt_api_key, decrypt_api_key

router = APIRouter(prefix="/models", tags=["Model Configuration"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pydantic Schemas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModelConfigCreate(BaseModel):
    provider: ProviderType
    provider_name: Optional[str] = None  # Custom display name
    config_name: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[SecretStr] = None
    api_base_url: Optional[str] = None
    local_server_url: Optional[str] = None  # For LOCAL type
    default_model: str = Field(..., min_length=1)
    available_models: List[str] = Field(default_factory=list)
    is_default: bool = False
    max_tokens: int = Field(default=4000, ge=100, le=128000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    
    @field_validator('api_base_url', 'local_server_url')
    @classmethod
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class ModelConfigUpdate(BaseModel):
    config_name: Optional[str] = None
    api_key: Optional[SecretStr] = None
    api_base_url: Optional[str] = None
    local_server_url: Optional[str] = None
    default_model: Optional[str] = None
    available_models: Optional[List[str]] = None
    is_default: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    status: Optional[str] = None


class ModelConfigResponse(BaseModel):
    id: str
    provider: str
    provider_name: Optional[str] = None
    config_name: str
    default_model: str
    api_base_url: Optional[str] = None
    available_models: List[str] = Field(default_factory=list)
    status: str
    is_default: bool
    settings: Dict[str, Any] = Field(default_factory=dict)
    last_tested: Optional[str] = None  # FIXED: Made optional
    total_usage: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


class ProviderInfo(BaseModel):
    id: str
    name: str
    display_name: str
    requires_api_key: bool
    requires_base_url: bool
    default_base_url: Optional[str] = None
    description: str
    popular_models: List[str]


class TestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    tokens: Optional[int] = None
    error: Optional[str] = None


class UniversalProviderCreate(BaseModel):
    """
    Universal schema for ANY provider not in standard list.
    """
    provider_name: str  # e.g., "Groq", "My Custom API"
    api_base_url: str   # OpenAI-compatible endpoint
    api_key: Optional[SecretStr] = None
    default_model: str
    config_name: Optional[str] = None
    is_default: bool = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/providers", response_model=List[ProviderInfo])
async def list_providers():
    """
    List ALL available provider types including popular third-party options.
    Frontend can also add any OpenAI-compatible provider via CUSTOM type.
    """
    providers = [
        # Major providers
        ProviderInfo(
            id=ProviderType.OPENAI.value,
            name="openai",
            display_name="OpenAI",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.openai.com/v1",
            description="GPT-4, GPT-3.5 Turbo, and other OpenAI models",
            popular_models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"]
        ),
        ProviderInfo(
            id=ProviderType.ANTHROPIC.value,
            name="anthropic",
            display_name="Anthropic Claude",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.anthropic.com/v1",
            description="Claude 3 Opus, Sonnet, Haiku - excellent reasoning",
            popular_models=["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
        ),
        ProviderInfo(
            id=ProviderType.GEMINI.value,
            name="gemini",
            display_name="Google Gemini",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            description="Google's multimodal models",
            popular_models=["gemini-pro", "gemini-pro-vision", "gemini-1.5-pro"]
        ),
        
        # High-performance third-party
        ProviderInfo(
            id=ProviderType.GROQ.value,
            name="groq",
            display_name="Groq",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.groq.com/openai/v1",
            description="Ultra-fast inference (100+ tokens/sec) with Llama 3",
            popular_models=["llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]
        ),
        ProviderInfo(
            id=ProviderType.MISTRAL.value,
            name="mistral",
            display_name="Mistral AI",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.mistral.ai/v1",
            description="European AI with Mistral and Mixtral models",
            popular_models=["mistral-large", "mistral-medium", "mistral-small", "codestral"]
        ),
        ProviderInfo(
            id=ProviderType.TOGETHER.value,
            name="together",
            display_name="Together AI",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.together.xyz/v1",
            description="Access to 100+ open-source models",
            popular_models=["meta-llama/Llama-3-70b", "mistralai/Mixtral-8x22B", "Qwen/Qwen2-72B"]
        ),
        ProviderInfo(
            id=ProviderType.COHERE.value,
            name="cohere",
            display_name="Cohere",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.cohere.ai/v1",
            description="Command R+ and Embed models",
            popular_models=["command-r", "command-r-plus", "command"]
        ),
        
        # Chinese/International
        ProviderInfo(
            id=ProviderType.MOONSHOT.value,
            name="moonshot",
            display_name="Moonshot (Kimi 2.5)",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.moonshot.cn/v1",
            description="Kimi 2.5 - Long context (200K+ tokens), Chinese/English",
            popular_models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
        ),
        ProviderInfo(
            id=ProviderType.DEEPSEEK.value,
            name="deepseek",
            display_name="DeepSeek",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url="https://api.deepseek.com/v1",
            description="DeepSeek Coder and Chat models",
            popular_models=["deepseek-chat", "deepseek-coder"]
        ),
        
        # Microsoft/Azure
        ProviderInfo(
            id=ProviderType.AZURE_OPENAI.value,
            name="azure_openai",
            display_name="Azure OpenAI",
            requires_api_key=True,
            requires_base_url=True,
            default_base_url=None,  # User-specific
            description="Enterprise OpenAI through Azure",
            popular_models=["gpt-4", "gpt-35-turbo"]
        ),
        
        # Local/Custom
        ProviderInfo(
            id=ProviderType.LOCAL.value,
            name="local",
            display_name="Local Model (Ollama/lmstudio)",
            requires_api_key=False,
            requires_base_url=True,
            default_base_url="http://localhost:11434/v1",
            description="Run models locally via Ollama, LM Studio, or llama.cpp",
            popular_models=["llama3", "mistral", "mixtral", "qwen2", "phi3"]
        ),
        ProviderInfo(
            id=ProviderType.CUSTOM.value,
            name="custom",
            display_name="Custom Provider (Any OpenAI-compatible)",
            requires_api_key=True,
            requires_base_url=True,
            default_base_url=None,
            description="Add any OpenAI-compatible API endpoint",
            popular_models=["custom-model"]
        ),
    ]
    return providers


@router.post("/configs", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config: ModelConfigCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """
    Save new model configuration from frontend.
    Supports ANY provider including custom OpenAI-compatible endpoints.
    """
    # Handle default flag
    if config.is_default:
        db.query(UserModelConfig).filter_by(
            user_id=user_id, 
            is_default=True
        ).update({"is_default": False})
        db.commit()
    
    # Encrypt API key if provided
    encrypted_key = None
    raw_key = None
    if config.api_key:
        raw_key = config.api_key.get_secret_value()
        if raw_key:
            encrypted_key = encrypt_api_key(raw_key)
    
    # Determine effective base URL
    effective_url = config.api_base_url or config.local_server_url
    
    db_config = UserModelConfig(
        user_id=user_id,
        provider=config.provider,
        provider_name=config.provider_name or config.provider.value,
        config_name=config.config_name,
        api_key_encrypted=encrypted_key,
        api_key_masked=f"...{raw_key[-4:]}" if (config.api_key and raw_key) else None,
        api_base_url=effective_url,
        local_server_url=config.local_server_url,
        default_model=config.default_model,
        available_models=config.available_models,
        is_default=config.is_default,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        timeout_seconds=config.timeout_seconds,
        status=ConnectionStatus.TESTING
    )
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # Test in background
    background_tasks.add_task(_test_config_async, db_config.id, user_id)
    
    return _serialize_config(db_config)


@router.post("/configs/universal", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_universal_config(
    config: UniversalProviderCreate,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """
    Universal endpoint for ANY OpenAI-compatible provider not in standard list.
    Examples: Perplexity, AI21, Anyscale, Fireworks, or your own API.
    """
    # Force unset other defaults
    if config.is_default:
        db.query(UserModelConfig).filter_by(
            user_id=user_id, 
            is_default=True
        ).update({"is_default": False})
    
    # Encrypt key
    encrypted_key = None
    raw_key = None
    if config.api_key:
        raw_key = config.api_key.get_secret_value()
        encrypted_key = encrypt_api_key(raw_key)
    
    db_config = UserModelConfig(
        user_id=user_id,
        provider=ProviderType.CUSTOM,
        provider_name=config.provider_name,
        config_name=config.config_name or f"{config.provider_name} Config",
        api_key_encrypted=encrypted_key,
        api_base_url=config.api_base_url,
        default_model=config.default_model,
        is_default=config.is_default,
        status=ConnectionStatus.TESTING
    )
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # Test immediately (not async for universal)
    result = await ModelService.test_connection(db_config)
    if not result["success"]:
        db_config.status = ConnectionStatus.ERROR
        db_config.last_error = result.get("error")
        db.commit()
    else:
        db_config.status = ConnectionStatus.ACTIVE
        db.commit()
    
    return _serialize_config(db_config)


async def _test_config_async(config_id: str, user_id: str):
    """Background task to test connection."""
    with next(get_db()) as db:
        config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
        if config:
            result = await ModelService.test_connection(config)
            if result["success"]:
                config.status = ConnectionStatus.ACTIVE
            else:
                config.status = ConnectionStatus.ERROR
                config.last_error = result.get("error", "Unknown error")
            db.commit()


def _serialize_config(config: UserModelConfig) -> Dict[str, Any]:
    """Serialize config to response format with safe defaults."""
    return {
        'id': str(config.id),
        'provider': config.provider.value if hasattr(config.provider, 'value') else str(config.provider),
        'provider_name': config.provider_name,
        'config_name': config.config_name,
        'default_model': config.default_model,
        'api_base_url': config.api_base_url,
        'available_models': config.available_models or [],
        'status': config.status.value if hasattr(config.status, 'value') else str(config.status),
        'is_default': config.is_default,
        'settings': {
            'max_tokens': config.max_tokens,
            'temperature': config.temperature,
            'top_p': config.top_p,
            'timeout': config.timeout_seconds
        },
        'last_tested': config.last_tested_at.isoformat() if hasattr(config, 'last_tested_at') and config.last_tested_at else None,
        'total_usage': {
            'requests': config.total_requests or 0,
            'tokens': config.total_tokens or 0,
            'cost_usd': round(config.estimated_cost_usd or 0, 4)
        }
    }


@router.get("/configs", response_model=List[ModelConfigResponse])
async def list_configs(
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """List user's model configurations."""
    configs = db.query(UserModelConfig).filter_by(user_id=user_id).all()
    return [_serialize_config(c) for c in configs]


@router.get("/configs/{config_id}", response_model=ModelConfigResponse)
async def get_config(config_id: str, db: Session = Depends(get_db), user_id: str = "sovereign"):
    """Get specific configuration."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return _serialize_config(config)


@router.put("/configs/{config_id}", response_model=ModelConfigResponse)
async def update_config(
    config_id: str,
    updates: ModelConfigUpdate,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Update configuration."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    if updates.is_default and not config.is_default:
        db.query(UserModelConfig).filter_by(user_id=user_id, is_default=True).update({"is_default": False})
    
    update_data = updates.model_dump(exclude_unset=True)
    
    if "api_key" in update_data and update_data["api_key"]:
        raw_key = update_data["api_key"].get_secret_value()
        if raw_key:
            config.api_key_encrypted = encrypt_api_key(raw_key)
            config.api_key_masked = f"...{raw_key[-4:]}"
        del update_data["api_key"]
    
    for field, value in update_data.items():
        if field in ['api_base_url', 'local_server_url'] and value:
            # Validate URL
            if not value.startswith(('http://', 'https://')):
                raise HTTPException(status_code=400, detail=f"Invalid URL: {value}")
        setattr(config, field, value)
    
    if "api_key_encrypted" in update_data:
        config.status = ConnectionStatus.TESTING
    
    db.commit()
    db.refresh(config)
    
    return _serialize_config(config)


@router.delete("/configs/{config_id}")
async def delete_config(config_id: str, db: Session = Depends(get_db), user_id: str = "sovereign"):
    """Delete configuration."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    remaining = db.query(UserModelConfig).filter_by(user_id=user_id).count()
    if remaining <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only configuration")
    
    db.delete(config)
    db.commit()
    return {"message": "Configuration deleted"}


@router.post("/configs/{config_id}/test", response_model=TestResult)
async def test_config(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Test specific configuration."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    result = await ModelService.test_connection(config)
    return TestResult(
        success=result["success"],
        message="Connection successful" if result["success"] else "Connection failed",
        latency_ms=result.get("latency_ms"),
        model=result.get("model"),
        tokens=result.get("tokens"),
        error=result.get("error")
    )


@router.post("/configs/{config_id}/fetch-models")
async def fetch_models(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """
    Dynamically fetch available models from provider API.
    Works for OpenAI, Groq, Together, and local Ollama.
    """
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    try:
        # Decrypt key for API call
        api_key = None
        if config.api_key_encrypted:
            api_key = decrypt_api_key(config.api_key_encrypted)
        
        models = await ModelService.list_models_for_provider(
            config.provider,
            api_key,
            config.get_effective_base_url()
        )
        
        # Update config with fetched models
        config.available_models = models
        db.commit()
        
        return {
            "provider": config.provider.value,
            "base_url": config.get_effective_base_url(),
            "models": models,
            "count": len(models)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.post("/configs/{config_id}/set-default")
async def set_default(config_id: str, db: Session = Depends(get_db), user_id: str = "sovereign"):
    """Set as default."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    db.query(UserModelConfig).filter_by(user_id=user_id, is_default=True).update({"is_default": False})
    config.is_default = True
    db.commit()
    
    return {"message": "Configuration set as default", "config_id": config_id}


@router.get("/configs/{config_id}/usage")
async def get_usage(
    config_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Get usage statistics."""
    config = db.query(UserModelConfig).filter_by(id=config_id, user_id=user_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    from datetime import datetime, timedelta
    
    since = datetime.utcnow() - timedelta(days=days)
    logs = db.query(ModelUsageLog).filter(
        ModelUsageLog.config_id == config_id,
        ModelUsageLog.created_at >= since
    ).all()
    
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(float(log.cost_usd or 0) for log in logs)
    
    daily = {}
    for log in logs:
        day = log.created_at.strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"tokens": 0, "requests": 0, "cost": 0.0}
        daily[day]["tokens"] += log.total_tokens
        daily[day]["requests"] += 1
        daily[day]["cost"] += float(log.cost_usd or 0)
    
    return {
        "period_days": days,
        "total_tokens": total_tokens,
        "total_requests": len(logs),
        "total_cost_usd": round(total_cost, 4),
        "success_rate": sum(1 for log in logs if log.success) / max(len(logs), 1) * 100,
        "daily_breakdown": daily,
        "by_model": {}
    }