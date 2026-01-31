"""
Model provider service.
Dynamically routes requests to user-configured APIs (OpenAI, Anthropic, Local).
"""

import os
import time
import json
from typing import Optional, Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod
from datetime import datetime

from backend.models.database import get_db_context
from backend.models.entities.user_config import UserModelConfig, ProviderType, ModelUsageLog


class BaseModelProvider(ABC):
    """Abstract base for model providers."""
    
    def __init__(self, config: UserModelConfig):
        self.config = config
        self.api_key = self._decrypt_key(config.api_key_encrypted) if config.api_key_encrypted else None
    
    def _decrypt_key(self, encrypted: str) -> str:
        # TODO: Implement proper encryption (fernet or similar)
        # For now, pretending it's encrypted but storing raw
        return encrypted
    
    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def stream_generate(self, system_prompt: str, user_message: str, **kwargs) -> AsyncGenerator[str, None]:
        pass


class OpenAIProvider(BaseModelProvider):
    async def generate(self, system_prompt: str, user_message: str, **kwargs) -> Dict[str, Any]:
        import openai
        
        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.config.api_base_url or "https://api.openai.com/v1"
        )
        
        start_time = time.time()
        try:
            response = await client.chat.completions.create(
                model=kwargs.get('model', self.config.default_model),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=kwargs.get('max_tokens', self.config.max_tokens),
                temperature=kwargs.get('temperature', self.config.temperature),
                timeout=self.config.timeout_seconds
            )
            
            latency = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            await self._log_usage(tokens, latency, success=True)
            
            return {
                "content": content,
                "tokens_used": tokens,
                "latency_ms": latency,
                "model": response.model
            }
            
        except Exception as e:
            await self._log_usage(0, 0, success=False, error=str(e))
            raise
    
    async def stream_generate(self, system_prompt: str, user_message: str, **kwargs):
        import openai
        
        client = openai.AsyncOpenAI(api_key=self.api_key)
        
        stream = await client.chat.completions.create(
            model=kwargs.get('model', self.config.default_model),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            stream=True,
            max_tokens=kwargs.get('max_tokens', self.config.max_tokens),
            temperature=kwargs.get('temperature', self.config.temperature)
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _log_usage(self, tokens: int, latency: int, success: bool, error: str = None):
        with get_db_context() as db:
            self.config.increment_usage(tokens)
            db.add(ModelUsageLog(
                config_id=self.config.id,
                provider=self.config.provider,
                model_used=self.config.default_model,
                total_tokens=tokens,
                latency_ms=latency,
                success=success,
                error_message=error,
                request_type="inference"
            ))
            db.commit()


class AnthropicProvider(BaseModelProvider):
    async def generate(self, system_prompt: str, user_message: str, **kwargs) -> Dict[str, Any]:
        import anthropic
        
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        start_time = time.time()
        response = await client.messages.create(
            model=kwargs.get('model', self.config.default_model),
            max_tokens=kwargs.get('max_tokens', self.config.max_tokens),
            temperature=kwargs.get('temperature', self.config.temperature),
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        latency = int((time.time() - start_time) * 1000)
        content = response.content[0].text if response.content else ""
        
        return {
            "content": content,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
            "latency_ms": latency,
            "model": response.model
        }
    
    async def stream_generate(self, system_prompt: str, user_message: str, **kwargs):
        import anthropic
        
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        async with client.messages.stream(
            model=kwargs.get('model', self.config.default_model),
            max_tokens=kwargs.get('max_tokens', self.config.max_tokens),
            temperature=kwargs.get('temperature', self.config.temperature),
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            async for text in stream.text_stream:
                yield text


class LocalProvider(BaseModelProvider):
    """For local models via OpenAI-compatible API (llama.cpp, vLLM, etc.)."""
    
    async def generate(self, system_prompt: str, user_message: str, **kwargs) -> Dict[str, Any]:
        import openai
        
        client = openai.AsyncOpenAI(
            base_url=self.config.local_server_url or "http://localhost:8000/v1",
            api_key="not-needed"  # Local models usually don't need auth
        )
        
        start_time = time.time()
        response = await client.chat.completions.create(
            model=kwargs.get('model', self.config.default_model),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=kwargs.get('max_tokens', self.config.max_tokens),
            temperature=kwargs.get('temperature', self.config.temperature)
        )
        
        latency = int((time.time() - start_time) * 1000)
        
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "latency_ms": latency,
            "model": response.model
        }
    
    async def stream_generate(self, system_prompt: str, user_message: str, **kwargs):
        import openai
        
        client = openai.AsyncOpenAI(
            base_url=self.config.local_server_url or "http://localhost:8000/v1",
            api_key="not-needed"
        )
        
        stream = await client.chat.completions.create(
            model=kwargs.get('model', self.config.default_model),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            stream=True,
            max_tokens=kwargs.get('max_tokens', self.config.max_tokens)
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Provider factory
PROVIDERS = {
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.LOCAL: LocalProvider,
    ProviderType.GEMINI: OpenAIProvider,  # Use OpenAI compatibility layer
}


class ModelService:
    """Service to manage model interactions with user-provided configs."""
    
    @staticmethod
    async def get_provider(user_id: str, preferred_config_id: Optional[str] = None) -> Optional[BaseModelProvider]:
        """Get provider instance for user."""
        with get_db_context() as db:
            if preferred_config_id:
                config = db.query(UserModelConfig).filter_by(
                    id=preferred_config_id, 
                    user_id=user_id,
                    status='active'
                ).first()
            else:
                # Get default config
                config = db.query(UserModelConfig).filter_by(
                    user_id=user_id,
                    is_default=True,
                    status='active'
                ).first()
            
            if not config:
                return None
            
            provider_class = PROVIDERS.get(config.provider)
            if not provider_class:
                raise ValueError(f"Unknown provider: {config.provider}")
            
            return provider_class(config)
    
    @staticmethod
    async def generate_with_agent(
        agent, 
        user_message: str, 
        user_id: str = "sovereign",
        config_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate response using agent's ethos and user-selected model."""
        provider = await ModelService.get_provider(user_id, config_id)
        
        if not provider:
            raise ValueError("No active model configuration found. Please configure in settings.")
        
        # Get system prompt from agent's ethos
        system_prompt = agent.ethos.mission_statement if agent.ethos else "You are an AI assistant."
        
        # Add behavioral rules to system prompt
        if agent.ethos:
            rules = agent.ethos.get_behavioral_rules()
            if rules:
                system_prompt += "\n\nRules:\n" + "\n".join(f"- {r}" for r in rules)
        
        return await provider.generate(system_prompt, user_message)
    
    @staticmethod
    async def test_connection(config: UserModelConfig) -> Dict[str, Any]:
        """Test a model configuration."""
        try:
            provider_class = PROVIDERS.get(config.provider)
            if not provider_class:
                return {"success": False, "error": "Unknown provider"}
            
            provider = provider_class(config)
            
            # Test with simple prompt
            result = await provider.generate(
                "You are a test assistant.",
                "Say 'Connection successful' and nothing else.",
                max_tokens=20
            )
            
            success = "successful" in result['content'].lower()
            config.mark_tested(success)
            
            return {
                "success": success,
                "latency_ms": result['latency_ms'],
                "model": result['model'],
                "response": result['content'][:100]
            }
            
        except Exception as e:
            config.mark_tested(False, str(e))
            return {
                "success": False,
                "error": str(e)
            }