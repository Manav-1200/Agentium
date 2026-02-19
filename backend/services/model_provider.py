"""
Universal Model Provider Service for Agentium.
Supports ANY OpenAI-compatible API provider.
"""

import os
import time
import json
from typing import Optional, Dict, Any, AsyncGenerator, List, Tuple
from abc import ABC, abstractmethod
from datetime import datetime

from backend.models.database import get_db_context
from backend.models.entities.user_config import UserModelConfig, ProviderType, ModelUsageLog


# ─────────────────────────────────────────────────────────────────────────────
# Per-model pricing table
# Prices are USD per 1 M tokens (input, output).
# Source: official provider pricing pages as of early 2026.
# ─────────────────────────────────────────────────────────────────────────────

# fmt: off
MODEL_PRICES: Dict[str, Tuple[float, float]] = {
    # ── OpenAI ───────────────────────────────────────────────────────────────
    # model-name: (input $/1M, output $/1M)
    "gpt-4o":                          (2.50,   10.00),
    "gpt-4o-2024-11-20":               (2.50,   10.00),
    "gpt-4o-2024-08-06":               (2.50,   10.00),
    "gpt-4o-mini":                     (0.15,    0.60),
    "gpt-4o-mini-2024-07-18":          (0.15,    0.60),
    "gpt-4-turbo":                     (10.00,  30.00),
    "gpt-4-turbo-preview":             (10.00,  30.00),
    "gpt-4-turbo-2024-04-09":          (10.00,  30.00),
    "gpt-4":                           (30.00,  60.00),
    "gpt-4-32k":                       (60.00, 120.00),
    "gpt-3.5-turbo":                   (0.50,   1.50),
    "gpt-3.5-turbo-instruct":          (1.50,   2.00),
    "o1":                              (15.00,  60.00),
    "o1-preview":                      (15.00,  60.00),
    "o1-mini":                         (3.00,   12.00),
    "o3-mini":                         (1.10,    4.40),

    # ── Anthropic ────────────────────────────────────────────────────────────
    "claude-3-5-sonnet-20241022":      (3.00,   15.00),
    "claude-3-5-sonnet-20240620":      (3.00,   15.00),
    "claude-3-5-haiku-20241022":       (0.80,    4.00),
    "claude-3-opus-20240229":          (15.00,  75.00),
    "claude-3-sonnet-20240229":        (3.00,   15.00),
    "claude-3-haiku-20240307":         (0.25,   1.25),
    "claude-2.1":                      (8.00,   24.00),
    "claude-2.0":                      (8.00,   24.00),

    # ── Google Gemini ─────────────────────────────────────────────────────────
    "gemini-1.5-pro":                  (1.25,    5.00),   # ≤128K context tier
    "gemini-1.5-pro-latest":           (1.25,    5.00),
    "gemini-1.5-flash":                (0.075,   0.30),
    "gemini-1.5-flash-latest":         (0.075,   0.30),
    "gemini-1.5-flash-8b":             (0.0375,  0.15),
    "gemini-1.0-pro":                  (0.50,    1.50),
    "gemini-2.0-flash":                (0.10,    0.40),
    "gemini-2.0-flash-lite":           (0.075,   0.30),

    # ── Groq (prices per 1 M tokens) ─────────────────────────────────────────
    "llama-3.3-70b-versatile":         (0.59,    0.79),
    "llama-3.1-70b-versatile":         (0.59,    0.79),
    "llama-3.1-8b-instant":            (0.05,    0.08),
    "llama3-70b-8192":                 (0.59,    0.79),
    "llama3-8b-8192":                  (0.05,    0.08),
    "mixtral-8x7b-32768":              (0.24,    0.24),
    "gemma2-9b-it":                    (0.20,    0.20),
    "gemma-7b-it":                     (0.07,    0.07),

    # ── Mistral AI ────────────────────────────────────────────────────────────
    "mistral-large-latest":            (2.00,    6.00),
    "mistral-medium-latest":           (2.70,    8.10),
    "mistral-small-latest":            (0.20,    0.60),
    "open-mistral-7b":                 (0.25,    0.25),
    "open-mixtral-8x7b":               (0.70,    0.70),
    "open-mixtral-8x22b":              (2.00,    6.00),
    "codestral-latest":                (0.20,    0.60),

    # ── Together AI ───────────────────────────────────────────────────────────
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo":  (0.88,  0.88),
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo":   (0.18,  0.18),
    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": (3.50,  3.50),
    "mistralai/Mixtral-8x7B-Instruct-v0.1":          (0.60,  0.60),
    "Qwen/Qwen2.5-72B-Instruct-Turbo":               (1.20,  1.20),

    # ── DeepSeek ──────────────────────────────────────────────────────────────
    "deepseek-chat":                   (0.27,    1.10),   # DeepSeek-V3
    "deepseek-reasoner":               (0.55,    2.19),   # DeepSeek-R1
    "deepseek-coder":                  (0.27,    1.10),

    # ── Moonshot (Kimi) ───────────────────────────────────────────────────────
    "moonshot-v1-8k":                  (1.63,    1.63),
    "moonshot-v1-32k":                 (3.26,    3.26),
    "moonshot-v1-128k":                (8.14,    8.14),

    # ── Cohere ────────────────────────────────────────────────────────────────
    "command-r-plus":                  (2.50,   10.00),
    "command-r":                       (0.15,    0.60),
    "command":                         (1.00,    2.00),

    # ── Local / free ─────────────────────────────────────────────────────────
    # All local models cost $0
}
# fmt: on

# Fallback blended rates ($/1M tokens) used when a model is not in the table.
# These are conservative estimates — real cost depends on the exact model.
_PROVIDER_FALLBACK_RATES: Dict[ProviderType, float] = {
    ProviderType.OPENAI:             5.00,
    ProviderType.ANTHROPIC:          9.00,
    ProviderType.GEMINI:             1.00,
    ProviderType.GROQ:               0.30,
    ProviderType.MISTRAL:            1.50,
    ProviderType.TOGETHER:           1.00,
    ProviderType.FIREWORKS:          0.90,
    ProviderType.PERPLEXITY:         1.00,
    ProviderType.AI21:               1.50,
    ProviderType.COHERE:             2.00,
    ProviderType.MOONSHOT:           3.00,
    ProviderType.DEEPSEEK:           0.70,
    ProviderType.QIANWEN:            1.00,
    ProviderType.ZHIPU:              1.00,
    ProviderType.AZURE_OPENAI:       5.00,
    ProviderType.CUSTOM:             1.00,
    ProviderType.OPENAI_COMPATIBLE:  1.00,
    ProviderType.LOCAL:              0.0,
}


def calculate_cost(
    model_name: str,
    provider: ProviderType,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Calculate the USD cost for an API call using per-model prices.

    Looks up the model in MODEL_PRICES (input/output split).
    Falls back to a blended per-provider rate when the model is unknown.
    Always returns 0.0 for local models.

    Args:
        model_name:        Exact model identifier returned by the API.
        provider:          ProviderType enum value.
        prompt_tokens:     Number of input/prompt tokens consumed.
        completion_tokens: Number of output/completion tokens generated.

    Returns:
        Estimated cost in USD (float, rounded to 8 decimal places).
    """
    if provider == ProviderType.LOCAL:
        return 0.0

    # Normalise: some APIs return versioned suffixes or capitalisation variants
    normalised = model_name.lower().strip()

    # 1. Exact match
    prices = MODEL_PRICES.get(model_name) or MODEL_PRICES.get(normalised)

    # 2. Prefix match — handles cases like "gpt-4o-2024-xx-xx" → "gpt-4o"
    if prices is None:
        for key, val in MODEL_PRICES.items():
            if normalised.startswith(key.lower()):
                prices = val
                break

    if prices is not None:
        input_rate, output_rate = prices
        cost = (prompt_tokens / 1_000_000) * input_rate + \
               (completion_tokens / 1_000_000) * output_rate
    else:
        # Fallback to blended provider rate
        blended = _PROVIDER_FALLBACK_RATES.get(provider, 1.00)
        total_tokens = prompt_tokens + completion_tokens
        cost = (total_tokens / 1_000_000) * blended

    return round(cost, 8)


# ─────────────────────────────────────────────────────────────────────────────
# Base provider
# ─────────────────────────────────────────────────────────────────────────────

class BaseModelProvider(ABC):
    """Abstract base for all model providers."""

    def __init__(self, config: UserModelConfig):
        self.config = config
        self.api_key = self._get_api_key() if config.requires_api_key() else None
        self.base_url = config.get_effective_base_url()

    def _get_api_key(self) -> Optional[str]:
        """Decrypt and return the stored API key."""
        if not self.config.api_key_encrypted:
            return None
        from backend.core.security import decrypt_api_key
        try:
            return decrypt_api_key(self.config.api_key_encrypted)
        except Exception:
            return None

    @abstractmethod
    async def generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def stream_generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        pass

    async def _log_usage(
        self,
        *,
        model_used: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        success: bool,
        error: Optional[str] = None,
        agentium_id: str = "system",
        request_type: str = "chat",
    ) -> None:
        """
        Persist a ModelUsageLog row and update the config's rolling counters.

        Uses the per-model price table to calculate exact cost from the
        input/output token split rather than a blended provider average.
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = calculate_cost(
            model_name=model_used,
            provider=self.config.provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        try:
            with get_db_context() as db:
                # Keep the config's running totals in sync
                self.config.increment_usage(total_tokens, cost_usd=cost)

                db.add(ModelUsageLog(
                    # agentium_id is auto-generated inside ModelUsageLog.__init__
                    config_id=self.config.id,
                    provider=self.config.provider,
                    model_used=model_used,
                    request_type=request_type,
                    total_tokens=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error,
                    cost_usd=cost,
                    request_metadata={"agentium_id": agentium_id},
                ))
                db.commit()
        except Exception as exc:
            # Logging must never crash the main request path
            print(f"⚠️  _log_usage failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI-compatible provider  (OpenAI, Groq, Mistral, Together, DeepSeek, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class OpenAICompatibleProvider(BaseModelProvider):
    """
    Universal provider for ANY OpenAI-compatible API endpoint.
    Works with Groq, Mistral, Together, Fireworks, DeepSeek, Moonshot, etc.
    """

    async def generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> Dict[str, Any]:
        import openai

        actual_model = kwargs.get("model", self.config.default_model)
        client = openai.AsyncOpenAI(
            api_key=self.api_key or "not-needed",
            base_url=self.base_url,
            timeout=self.config.timeout_seconds,
        )

        start_time = time.time()
        try:
            response = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                top_p=kwargs.get("top_p", self.config.top_p),
            )

            latency = int((time.time() - start_time) * 1000)
            content  = response.choices[0].message.content or ""
            prompt_tokens     = response.usage.prompt_tokens     if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            returned_model    = response.model or actual_model

            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                agentium_id=kwargs.get("agentium_id", "system"),
            )

            return {
                "content":       content,
                "tokens_used":   prompt_tokens + completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms":    latency,
                "model":         returned_model,
                "finish_reason": response.choices[0].finish_reason,
                "cost_usd":      calculate_cost(
                    returned_model, self.config.provider,
                    prompt_tokens, completion_tokens
                ),
            }

        except Exception as exc:
            await self._log_usage(
                model_used=actual_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(exc),
                agentium_id=kwargs.get("agentium_id", "system"),
            )
            raise

    async def stream_generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        import openai

        actual_model = kwargs.get("model", self.config.default_model)
        client = openai.AsyncOpenAI(
            api_key=self.api_key or "not-needed",
            base_url=self.base_url,
            timeout=self.config.timeout_seconds,
        )

        start_time = time.time()
        prompt_tokens     = 0
        completion_tokens = 0
        returned_model    = actual_model

        try:
            stream = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                stream=True,
                stream_options={"include_usage": True},   # Request token counts in stream
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
            )

            async for chunk in stream:
                # Final chunk carries usage when include_usage=True
                if chunk.usage:
                    prompt_tokens     = chunk.usage.prompt_tokens     or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
                if chunk.model:
                    returned_model = chunk.model
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        finally:
            latency = int((time.time() - start_time) * 1000)
            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                request_type="stream",
                agentium_id=kwargs.get("agentium_id", "system"),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic provider
# ─────────────────────────────────────────────────────────────────────────────

class AnthropicProvider(BaseModelProvider):
    """Anthropic Claude API (native SDK)."""

    async def generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> Dict[str, Any]:
        import anthropic

        actual_model = kwargs.get("model", self.config.default_model)
        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        start_time = time.time()
        try:
            response = await client.messages.create(
                model=actual_model,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            latency           = int((time.time() - start_time) * 1000)
            content           = response.content[0].text if response.content else ""
            prompt_tokens     = response.usage.input_tokens  if response.usage else 0
            completion_tokens = response.usage.output_tokens if response.usage else 0
            returned_model    = response.model or actual_model

            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                agentium_id=kwargs.get("agentium_id", "system"),
            )

            return {
                "content":           content,
                "tokens_used":       prompt_tokens + completion_tokens,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms":        latency,
                "model":             returned_model,
                "cost_usd":          calculate_cost(
                    returned_model, self.config.provider,
                    prompt_tokens, completion_tokens
                ),
            }

        except Exception as exc:
            await self._log_usage(
                model_used=actual_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(exc),
                agentium_id=kwargs.get("agentium_id", "system"),
            )
            raise

    async def stream_generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        import anthropic

        actual_model = kwargs.get("model", self.config.default_model)
        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        start_time        = time.time()
        prompt_tokens     = 0
        completion_tokens = 0
        returned_model    = actual_model

        try:
            async with client.messages.stream(
                model=actual_model,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

                # get_final_message() is available after the stream exhausts
                final = await stream.get_final_message()
                if final.usage:
                    prompt_tokens     = final.usage.input_tokens
                    completion_tokens = final.usage.output_tokens
                returned_model = final.model or actual_model

        finally:
            latency = int((time.time() - start_time) * 1000)
            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                request_type="stream",
                agentium_id=kwargs.get("agentium_id", "system"),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Google Gemini provider
# ─────────────────────────────────────────────────────────────────────────────

class GeminiProvider(BaseModelProvider):
    """Google Gemini via the OpenAI-compatibility layer."""

    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    async def generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> Dict[str, Any]:
        import openai

        actual_model = kwargs.get("model", self.config.default_model)
        base_url = self.config.api_base_url or self._BASE_URL

        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
            timeout=self.config.timeout_seconds,
        )

        start_time = time.time()
        try:
            response = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )

            latency           = int((time.time() - start_time) * 1000)
            content           = response.choices[0].message.content or ""
            prompt_tokens     = response.usage.prompt_tokens     if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            returned_model    = response.model or actual_model

            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                agentium_id=kwargs.get("agentium_id", "system"),
            )

            return {
                "content":           content,
                "tokens_used":       prompt_tokens + completion_tokens,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms":        latency,
                "model":             returned_model,
                "cost_usd":          calculate_cost(
                    returned_model, self.config.provider,
                    prompt_tokens, completion_tokens
                ),
            }

        except Exception as exc:
            await self._log_usage(
                model_used=actual_model,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(exc),
                agentium_id=kwargs.get("agentium_id", "system"),
            )
            raise

    async def stream_generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        import openai

        actual_model = kwargs.get("model", self.config.default_model)
        base_url     = self.config.api_base_url or self._BASE_URL

        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )

        start_time        = time.time()
        prompt_tokens     = 0
        completion_tokens = 0
        returned_model    = actual_model

        try:
            stream = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )

            async for chunk in stream:
                if chunk.usage:
                    prompt_tokens     = chunk.usage.prompt_tokens     or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
                if chunk.model:
                    returned_model = chunk.model
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        finally:
            latency = int((time.time() - start_time) * 1000)
            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                request_type="stream",
                agentium_id=kwargs.get("agentium_id", "system"),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Local provider  (Ollama, llama.cpp, LM Studio, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class LocalProvider(OpenAICompatibleProvider):
    """
    Local models served via OpenAI-compatible endpoints.
    Always costs $0; tokens are still tracked for budget/rate-limit purposes.
    Falls back to raw Ollama HTTP API if the OpenAI-compat path fails.
    """

    async def generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> Dict[str, Any]:
        import openai

        actual_model = kwargs.get("model", self.config.default_model)
        # Many local servers need the system prompt folded into the user turn
        combined_prompt = f"{system_prompt}\n\nUser: {user_message}"

        client = openai.AsyncOpenAI(
            base_url=self.base_url or "http://localhost:11434/v1",
            api_key="ollama",   # Required field; value ignored by local servers
        )

        start_time = time.time()
        try:
            response = await client.chat.completions.create(
                model=actual_model,
                messages=[{"role": "user", "content": combined_prompt}],
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
            )

            latency           = int((time.time() - start_time) * 1000)
            content           = response.choices[0].message.content or ""
            prompt_tokens     = response.usage.prompt_tokens     if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            # If the local server doesn't return usage, approximate from word count
            if prompt_tokens == 0 and completion_tokens == 0:
                prompt_tokens     = len(combined_prompt.split())
                completion_tokens = len(content.split())
            returned_model = response.model or actual_model

            await self._log_usage(
                model_used=returned_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                agentium_id=kwargs.get("agentium_id", "system"),
            )

            return {
                "content":           content,
                "tokens_used":       prompt_tokens + completion_tokens,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms":        latency,
                "model":             returned_model,
                "cost_usd":          0.0,
            }

        except Exception:
            return await self._fallback_local_generate(
                system_prompt, user_message, kwargs
            )

    async def _fallback_local_generate(
        self, system_prompt: str, user_message: str, kwargs: dict
    ) -> Dict[str, Any]:
        """Raw HTTP fallback for Ollama /api/generate endpoint."""
        import aiohttp

        url = (
            f"{self.base_url}/generate"
            if self.base_url
            else "http://localhost:11434/api/generate"
        )
        # Normalise: strip trailing /v1 so we hit the Ollama native API
        url = url.replace("/v1/generate", "/api/generate")

        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "model":  self.config.default_model,
                    "prompt": f"{system_prompt}\n\nUser: {user_message}\nAssistant:",
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", self.config.temperature),
                        "num_predict": kwargs.get("max_tokens",  self.config.max_tokens),
                    },
                },
            ) as response:
                data = await response.json()

        latency           = int((time.time() - start_time) * 1000)
        content           = data.get("response", "")
        completion_tokens = data.get("eval_count",   0)
        prompt_tokens     = data.get("prompt_eval_count", 0)

        await self._log_usage(
            model_used=self.config.default_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency,
            success=True,
            agentium_id=kwargs.get("agentium_id", "system"),
        )

        return {
            "content":           content,
            "tokens_used":       prompt_tokens + completion_tokens,
            "prompt_tokens":     prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms":        latency,
            "model":             self.config.default_model,
            "cost_usd":          0.0,
        }

    async def stream_generate(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream from local server; token logging at end of stream."""
        import openai

        actual_model    = kwargs.get("model", self.config.default_model)
        combined_prompt = f"{system_prompt}\n\nUser: {user_message}"

        client = openai.AsyncOpenAI(
            base_url=self.base_url or "http://localhost:11434/v1",
            api_key="ollama",
        )

        start_time        = time.time()
        prompt_tokens     = 0
        completion_tokens = 0
        content_so_far    = []

        try:
            stream = await client.chat.completions.create(
                model=actual_model,
                messages=[{"role": "user", "content": combined_prompt}],
                stream=True,
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
            )

            async for chunk in stream:
                if chunk.usage:
                    prompt_tokens     = chunk.usage.prompt_tokens     or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
                if chunk.choices and chunk.choices[0].delta.content:
                    token_text = chunk.choices[0].delta.content
                    content_so_far.append(token_text)
                    yield token_text

        finally:
            # Approximate if the server didn't return usage data
            if prompt_tokens == 0 and completion_tokens == 0:
                prompt_tokens     = len(combined_prompt.split())
                completion_tokens = len("".join(content_so_far).split())

            latency = int((time.time() - start_time) * 1000)
            await self._log_usage(
                model_used=actual_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency,
                success=True,
                request_type="stream",
                agentium_id=kwargs.get("agentium_id", "system"),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Provider factory map
# ─────────────────────────────────────────────────────────────────────────────

PROVIDERS: Dict[ProviderType, type] = {
    # Native SDK providers
    ProviderType.ANTHROPIC:          AnthropicProvider,
    ProviderType.GEMINI:             GeminiProvider,

    # OpenAI-compatible endpoints
    ProviderType.OPENAI:             OpenAICompatibleProvider,
    ProviderType.GROQ:               OpenAICompatibleProvider,
    ProviderType.MISTRAL:            OpenAICompatibleProvider,
    ProviderType.COHERE:             OpenAICompatibleProvider,
    ProviderType.TOGETHER:           OpenAICompatibleProvider,
    ProviderType.FIREWORKS:          OpenAICompatibleProvider,
    ProviderType.PERPLEXITY:         OpenAICompatibleProvider,
    ProviderType.AI21:               OpenAICompatibleProvider,
    ProviderType.MOONSHOT:           OpenAICompatibleProvider,
    ProviderType.DEEPSEEK:           OpenAICompatibleProvider,
    ProviderType.QIANWEN:            OpenAICompatibleProvider,
    ProviderType.ZHIPU:              OpenAICompatibleProvider,
    ProviderType.AZURE_OPENAI:       OpenAICompatibleProvider,
    ProviderType.CUSTOM:             OpenAICompatibleProvider,
    ProviderType.OPENAI_COMPATIBLE:  OpenAICompatibleProvider,

    # Local inference servers
    ProviderType.LOCAL:              LocalProvider,
}


# ─────────────────────────────────────────────────────────────────────────────
# ModelService
# ─────────────────────────────────────────────────────────────────────────────

class ModelService:
    """High-level service that wires agents to providers."""

    @staticmethod
    async def get_provider(
        user_id: str,
        preferred_config_id: Optional[str] = None,
    ) -> Optional[BaseModelProvider]:
        """Return a ready-to-use provider for the given user / config."""
        with get_db_context() as db:
            if preferred_config_id:
                config = db.query(UserModelConfig).filter_by(
                    id=preferred_config_id,
                    user_id=user_id,
                    status="active",
                ).first()
            else:
                config = db.query(UserModelConfig).filter_by(
                    user_id=user_id,
                    is_default=True,
                    status="active",
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
        config_id: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a response using an agent's ethos as the system prompt."""
        provider = await ModelService.get_provider(user_id, config_id)

        if not provider:
            raise ValueError(
                "No active model configuration found. "
                "Please configure a provider in settings."
            )

        system_prompt = system_prompt_override or (
            agent.ethos.mission_statement
            if agent.ethos
            else "You are an AI assistant."
        )

        if agent.ethos:
            try:
                rules = (
                    json.loads(agent.ethos.behavioral_rules)
                    if agent.ethos.behavioral_rules
                    else []
                )
                if rules:
                    system_prompt += "\n\nBehavioral Rules:\n" + "\n".join(
                        f"- {r}" for r in rules[:10]
                    )
            except Exception:
                pass

        return await provider.generate(
            system_prompt,
            user_message,
            agentium_id=getattr(agent, "agentium_id", "system"),
        )

    @staticmethod
    async def test_connection(config: UserModelConfig) -> Dict[str, Any]:
        """Smoke-test a provider configuration with a minimal request."""
        try:
            provider_class = PROVIDERS.get(config.provider)
            if not provider_class:
                return {"success": False, "error": f"Unknown provider: {config.provider}"}

            provider = provider_class(config)
            result = await provider.generate(
                "You are a test assistant.",
                "Say 'Connection successful' and nothing else.",
                max_tokens=20,
            )

            success = (
                "successful" in result["content"].lower()
                or len(result["content"]) > 0
            )
            config.mark_tested(success)

            return {
                "success":    success,
                "latency_ms": result["latency_ms"],
                "model":      result["model"],
                "response":   result["content"][:100],
                "tokens":     result["tokens_used"],
                "cost_usd":   result.get("cost_usd", 0.0),
            }

        except Exception as exc:
            config.mark_tested(False, str(exc))
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    async def list_models_for_provider(
        provider: ProviderType,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> List[str]:
        """
        Fetch available models from the provider API.
        Falls back to sensible defaults when the API call fails or no key
        is supplied.
        """
        try:
            if provider == ProviderType.OPENAI:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(api_key=api_key)
                models = await client.models.list()
                return sorted([
                    m.id for m in models.data
                    if any(x in m.id.lower() for x in ["gpt-4", "gpt-3.5", "o1", "o3"])
                ])

            elif provider == ProviderType.GROQ:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            elif provider == ProviderType.MISTRAL:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.mistral.ai/v1",
                )
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            elif provider == ProviderType.TOGETHER:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.together.xyz/v1",
                )
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            elif provider == ProviderType.DEEPSEEK:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1",
                )
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            elif provider == ProviderType.MOONSHOT:
                if not api_key:
                    return ModelService._get_default_models(provider)
                import openai
                client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.moonshot.cn/v1",
                )
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            elif provider == ProviderType.ANTHROPIC:
                # No public models.list endpoint — return known models
                return ModelService._get_default_models(provider)

            elif provider == ProviderType.GEMINI:
                # OpenAI-compat layer has limited model listing; use known list
                return ModelService._get_default_models(provider)

            elif provider == ProviderType.LOCAL:
                import aiohttp
                url = base_url or "http://localhost:11434"
                if url.endswith("/v1"):
                    url = url[:-3]

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}/api/tags",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data   = await resp.json()
                            models = [m["name"] for m in data.get("models", [])]
                            return sorted(models) if models else ModelService._get_default_models(provider)
                        return ModelService._get_default_models(provider)

            elif provider in [ProviderType.CUSTOM, ProviderType.OPENAI_COMPATIBLE]:
                if not base_url or not api_key:
                    return ["custom-model-1", "custom-model-2"]
                import openai
                client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
                models = await client.models.list()
                return sorted([m.id for m in models.data])

            else:
                return ModelService._get_default_models(provider)

        except Exception as exc:
            print(f"Error fetching models for {provider}: {exc}")
            return ModelService._get_default_models(provider)

    @staticmethod
    def _get_default_models(provider: ProviderType) -> List[str]:
        """Sensible default model lists when provider API is unreachable."""
        defaults: Dict[ProviderType, List[str]] = {
            ProviderType.OPENAI: [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
                "o1-mini",
                "o3-mini",
            ],
            ProviderType.ANTHROPIC: [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            ProviderType.GROQ: [
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
            ],
            ProviderType.MISTRAL: [
                "mistral-large-latest",
                "mistral-medium-latest",
                "mistral-small-latest",
                "open-mistral-7b",
                "codestral-latest",
            ],
            ProviderType.TOGETHER: [
                "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "Qwen/Qwen2.5-72B-Instruct-Turbo",
            ],
            ProviderType.GEMINI: [
                "gemini-2.0-flash",
                "gemini-1.5-pro-latest",
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash-8b",
                "gemini-1.0-pro",
            ],
            ProviderType.MOONSHOT: [
                "moonshot-v1-128k",
                "moonshot-v1-32k",
                "moonshot-v1-8k",
            ],
            ProviderType.DEEPSEEK: [
                "deepseek-chat",
                "deepseek-reasoner",
                "deepseek-coder",
            ],
            ProviderType.LOCAL: [
                "llama3.2",
                "llama3.1",
                "mistral",
                "qwen2.5",
                "phi3",
            ],
            ProviderType.COHERE: [
                "command-r-plus",
                "command-r",
                "command",
            ],
        }
        return defaults.get(provider, ["model-1", "model-2"])