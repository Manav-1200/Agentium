"""
User configuration and model connection management.
Stores API keys and model preferences set via frontend.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship, validates
from backend.models.entities.base import BaseEntity
import enum

class ProviderType(str, enum.Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    LOCAL = "local"
    AZURE = "azure"
    CUSTOM = "custom"

class ConnectionStatus(str, enum.Enum):
    """Status of model connection."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"

class UserModelConfig(BaseEntity):
    """
    Stores user's model configurations and API credentials.
    One record per provider. API keys stored encrypted.
    """
    
    __tablename__ = 'user_model_configs'
    
    # Identification
    user_id = Column(String(100), nullable=False, index=True)  # "sovereign" or user ID
    provider = Column(Enum(ProviderType), nullable=False)
    config_name = Column(String(100), nullable=False)  # "My OpenAI", "Local Llama"
    is_default = Column(Boolean, default=False)
    
    # Credentials (encrypt before storing)
    api_key_encrypted = Column(Text, nullable=True)
    api_base_url = Column(String(500), nullable=True)  # For custom/local endpoints
    
    # Model settings
    default_model = Column(String(100), nullable=False)  # "gpt-4", "claude-3-opus"
    available_models = Column(JSON, default=list)  # ["gpt-4", "gpt-3.5-turbo"]
    
    # Local model specific
    local_model_path = Column(String(500), nullable=True)
    local_server_url = Column(String(500), nullable=True)  # e.g., "http://localhost:8000/v1"
    
    # Inference settings
    max_tokens = Column(Integer, default=4000)
    temperature = Column(Float, default=0.7)
    timeout_seconds = Column(Integer, default=60)
    
    # Status
    status = Column(Enum(ConnectionStatus), default=ConnectionStatus.INACTIVE)
    last_tested_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Usage tracking
    tokens_used_total = Column(Integer, default=0)
    requests_count = Column(Integer, default=0)
    
    def mark_tested(self, success: bool, error: str = None):
        self.last_tested_at = datetime.utcnow()
        self.status = ConnectionStatus.ACTIVE if success else ConnectionStatus.ERROR
        self.last_error = error
    
    def increment_usage(self, tokens: int):
        self.tokens_used_total += tokens
        self.requests_count += 1
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'id': self.id,
            'provider': self.provider.value,
            'config_name': self.config_name,
            'is_default': self.is_default,
            'default_model': self.default_model,
            'available_models': self.available_models,
            'settings': {
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
                'timeout': self.timeout_seconds
            },
            'local_config': {
                'model_path': self.local_model_path,
                'server_url': self.local_server_url
            } if self.provider == ProviderType.LOCAL else None,
            'status': self.status.value,
            'last_tested': self.last_tested_at.isoformat() if self.last_tested_at else None,
            'usage': {
                'tokens_total': self.tokens_used_total,
                'requests': self.requests_count
            }
        })
        
        if include_sensitive:
            base['api_base_url'] = self.api_base_url
            base['api_key_present'] = bool(self.api_key_encrypted)
            
        return base


class ModelUsageLog(BaseEntity):
    """Audit log for all model API calls."""
    
    __tablename__ = 'model_usage_logs'
    
    config_id = Column(String(36), ForeignKey('user_model_configs.id'), nullable=False)
    agent_id = Column(String(36), ForeignKey('agents.id'), nullable=True)
    
    provider = Column(Enum(ProviderType), nullable=False)
    model_used = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(String(20), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    
    request_type = Column(String(50), nullable=False)  # "task", "deliberation", etc.
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    config = relationship("UserModelConfig")