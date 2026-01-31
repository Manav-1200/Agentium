"""
API routes for model configuration (frontend-managed).
Allows users to configure API keys, select providers, and test connections.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, SecretStr, Field
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
    config_name: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[SecretStr] = None
    api_base_url: Optional[str] = None
    default_model: str = Field(..., min_length=1)
    available_models: List[str] = Field(default_factory=list)
    local_server_url: Optional[str] = None
    is_default: bool = False
    max_tokens: int = Field(default=4000, ge=100, le=32000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider": "openai",
                "config_name": "Production OpenAI",
                "api_key": "sk-...",
                "default_model": "gpt-4",
                "available_models": ["gpt-4", "gpt-3.5-turbo"],
                "is_default": True
            }
        }


class ModelConfigUpdate(BaseModel):
    config_name: Optional[str] = None
    api_key: Optional[SecretStr] = None
    default_model: Optional[str] = None
    available_models: Optional[List[str]] = None
    is_default: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    status: Optional[str] = None


class ModelConfigResponse(BaseModel):
    id: str
    provider: str
    config_name: str
    default_model: str
    available_models: List[str]
    status: str
    is_default: bool
    settings: dict
    local_config: Optional[dict]
    usage: dict
    last_tested: Optional[str]
    
    class Config:
        from_attributes = True


class ProviderInfo(BaseModel):
    id: str
    name: str
    requires_api_key: bool
    supports_local: bool
    default_models: List[str]


class TestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/providers", response_model=List[ProviderInfo])
async def list_providers():
    """List available AI provider types with metadata."""
    providers = [
        ProviderInfo(
            id=ProviderType.OPENAI.value,
            name="OpenAI",
            requires_api_key=True,
            supports_local=False,
            default_models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
        ),
        ProviderInfo(
            id=ProviderType.ANTHROPIC.value,
            name="Anthropic",
            requires_api_key=True,
            supports_local=False,
            default_models=["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
        ),
        ProviderInfo(
            id=ProviderType.GEMINI.value,
            name="Google Gemini",
            requires_api_key=True,
            supports_local=False,
            default_models=["gemini-pro", "gemini-pro-vision"]
        ),
        ProviderInfo(
            id=ProviderType.LOCAL.value,
            name="Local Model (OpenAI-compatible)",
            requires_api_key=False,
            supports_local=True,
            default_models=["local-model", "llama-2", "mistral", "mixtral"]
        ),
        ProviderInfo(
            id=ProviderType.AZURE.value,
            name="Azure OpenAI",
            requires_api_key=True,
            supports_local=False,
            default_models=["gpt-4", "gpt-35-turbo"]
        ),
        ProviderInfo(
            id=ProviderType.CUSTOM.value,
            name="Custom Endpoint",
            requires_api_key=True,
            supports_local=True,
            default_models=["custom"]
        )
    ]
    return providers


@router.post("/configs", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config: ModelConfigCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"  # TODO: Get from JWT token
):
    """
    Save new model configuration from frontend.
    Encrypts API key and tests connection.
    """
    # If setting as default, unset others
    if config.is_default:
        db.query(UserModelConfig).filter_by(
            user_id=user_id, 
            is_default=True
        ).update({"is_default": False})
        db.commit()
    
    # Encrypt API key if provided
    encrypted_key = None
    if config.api_key:
        raw_key = config.api_key.get_secret_value()
        if raw_key:
            encrypted_key = encrypt_api_key(raw_key)
    
    # Create config
    db_config = UserModelConfig(
        user_id=user_id,
        provider=config.provider,
        config_name=config.config_name,
        api_key_encrypted=encrypted_key,
        api_base_url=config.api_base_url,
        default_model=config.default_model,
        available_models=config.available_models,
        local_server_url=config.local_server_url,
        is_default=config.is_default,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        status=ConnectionStatus.TESTING
    )
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # Test connection in background
    async def test_and_update():
        try:
            # Decrypt key for testing
            if db_config.api_key_encrypted:
                test_key = decrypt_api_key(db_config.api_key_encrypted)
                db_config.api_key_encrypted = encrypt_api_key(test_key)  # Re-encrypt
            
            result = await ModelService.test_connection(db_config)
            
            if result["success"]:
                db_config.mark_tested(True)
            else:
                db_config.mark_tested(False, result.get("error"))
            db.commit()
        except Exception as e:
            db_config.mark_tested(False, str(e))
            db.commit()
    
    background_tasks.add_task(test_and_update)
    
    return db_config


@router.get("/configs", response_model=List[ModelConfigResponse])
async def list_configs(
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """List user's model configurations (API keys hidden)."""
    configs = db.query(UserModelConfig).filter_by(user_id=user_id).all()
    return configs


@router.get("/configs/{config_id}", response_model=ModelConfigResponse)
async def get_config(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Get specific configuration details."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return config


@router.put("/configs/{config_id}", response_model=ModelConfigResponse)
async def update_config(
    config_id: str,
    updates: ModelConfigUpdate,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Update existing configuration."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Handle default flag change
    if updates.is_default and not config.is_default:
        db.query(UserModelConfig).filter_by(
            user_id=user_id, 
            is_default=True
        ).update({"is_default": False})
    
    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    
    if "api_key" in update_data and update_data["api_key"]:
        raw_key = update_data["api_key"].get_secret_value()
        if raw_key:
            config.api_key_encrypted = encrypt_api_key(raw_key)
        del update_data["api_key"]
    
    for field, value in update_data.items():
        setattr(config, field, value)
    
    # Reset status if key changed
    if "api_key_encrypted" in update_data:
        config.status = ConnectionStatus.TESTING
    
    db.commit()
    db.refresh(config)
    return config


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Remove a configuration."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Cannot delete if it's the only config
    remaining = db.query(UserModelConfig).filter_by(user_id=user_id).count()
    if remaining <= 1:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete the only configuration. Create another first."
        )
    
    db.delete(config)
    db.commit()
    
    return {"message": "Configuration deleted successfully"}


@router.post("/configs/{config_id}/test", response_model=TestResult)
async def test_config(
    config_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Test a specific configuration."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    try:
        result = await ModelService.test_connection(config)
        return TestResult(
            success=result["success"],
            message="Connection successful" if result["success"] else "Connection failed",
            latency_ms=result.get("latency_ms"),
            model=result.get("model"),
            error=result.get("error")
        )
    except Exception as e:
        return TestResult(
            success=False,
            message="Test failed",
            error=str(e)
        )


@router.get("/configs/{config_id}/usage")
async def get_config_usage(
    config_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Get usage statistics for a configuration."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
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
    total_requests = len(logs)
    
    # Group by day
    daily_usage = {}
    for log in logs:
        day = log.created_at.strftime("%Y-%m-%d")
        if day not in daily_usage:
            daily_usage[day] = {"tokens": 0, "requests": 0, "cost": 0.0}
        daily_usage[day]["tokens"] += log.total_tokens
        daily_usage[day]["requests"] += 1
        daily_usage[day]["cost"] += float(log.cost_usd or 0)
    
    return {
        "period_days": days,
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "total_cost_usd": round(total_cost, 4),
        "success_rate": sum(1 for log in logs if log.success) / max(len(logs), 1) * 100,
        "daily_breakdown": daily_usage
    )


@router.post("/configs/{config_id}/set-default")
async def set_default_config(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Set a configuration as the default."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Unset current default
    db.query(UserModelConfig).filter_by(
        user_id=user_id, 
        is_default=True
    ).update({"is_default": False})
    
    config.is_default = True
    db.commit()
    
    return {"message": "Configuration set as default"}


@router.get("/configs/{config_id}/models")
async def list_available_models(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """
    Fetch available models from provider API.
    For OpenAI/Anthropic, this makes an API call to list models.
    """
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    try:
        # This would actually fetch from the provider
        # For now, return stored available_models
        return {
            "provider": config.provider.value,
            "models": config.available_models,
            "default": config.default_model
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))