"""
API routes for model configuration (frontend-managed).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.user_config import UserModelConfig, ProviderType, ModelUsageLog
from backend.services.model_provider import ModelService, PROVIDERS

router = APIRouter(prefix="/models", tags=["models"])


class ModelConfigCreate(BaseModel):
    provider: ProviderType
    config_name: str
    api_key: Optional[SecretStr] = None
    api_base_url: Optional[str] = None
    default_model: str
    local_server_url: Optional[str] = None
    is_default: bool = False
    max_tokens: int = 4000
    temperature: float = 0.7


class ModelConfigResponse(BaseModel):
    id: str
    provider: str
    config_name: str
    default_model: str
    status: str
    is_default: bool
    
    class Config:
        from_attributes = True


@router.post("/configs", response_model=ModelConfigResponse)
async def create_config(
    config: ModelConfigCreate,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"  # TODO: Get from auth
):
    """Save new model configuration from frontend."""
    # If setting as default, unset others
    if config.is_default:
        db.query(UserModelConfig).filter_by(
            user_id=user_id, 
            is_default=True
        ).update({"is_default": False})
    
    db_config = UserModelConfig(
        user_id=user_id,
        provider=config.provider,
        config_name=config.config_name,
        api_key_encrypted=config.api_key.get_secret_value() if config.api_key else None,
        api_base_url=config.api_base_url,
        default_model=config.default_model,
        local_server_url=config.local_server_url,
        is_default=config.is_default,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        status="inactive"  # Will test after creation
    )
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # Test the connection
    test_result = await ModelService.test_connection(db_config)
    db.commit()
    
    if not test_result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {test_result.get('error', 'Unknown error')}"
        )
    
    return db_config


@router.get("/configs", response_model=List[ModelConfigResponse])
async def list_configs(
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """List user's model configurations."""
    configs = db.query(UserModelConfig).filter_by(user_id=user_id).all()
    return configs


@router.post("/configs/{config_id}/test")
async def test_config(
    config_id: str,
    db: Session = Depends(get_db),
    user_id: str = "sovereign"
):
    """Test a specific configuration."""
    config = db.query(UserModelConfig).filter_by(
        id=config_id, 
        user_id=user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    result = await ModelService.test_connection(config)
    db.commit()
    
    return result


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
        raise HTTPException(status_code=404, detail="Config not found")
    
    db.delete(config)
    db.commit()
    
    return {"message": "Configuration deleted"}


@router.get("/providers")
async def list_providers():
    """List available provider types."""
    return [
        {
            "id": p.value,
            "name": p.value.title(),
            "requires_api_key": p not in [ProviderType.LOCAL],
            "supports_local": p == ProviderType.LOCAL
        }
        for p in ProviderType
    ]