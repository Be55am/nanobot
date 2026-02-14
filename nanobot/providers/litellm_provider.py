"""LiteLLM provider implementation for multi-provider support with multiple fallbacks."""

import json
import os
from typing import Any

import litellm
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.providers.registry import find_by_model, find_gateway


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.

    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.

    NEW: Supports multiple fallback providers in priority order for high availability.
    """

    def __init__(
            self,
            api_key: str | None = None,
            api_base: str | None = None,
            default_model: str = "anthropic/claude-opus-4-5",
            extra_headers: dict[str, str] | None = None,
            provider_name: str | None = None,
            # NEW: Multiple fallbacks configuration
            fallbacks: list[dict[str, Any]] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.provider_name = provider_name

        # NEW: Store fallback configurations
        self.fallbacks = fallbacks or []

        # Detect gateway / local deployment.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # NEW: Detect gateways for all fallbacks
        self._fallback_gateways = []
        for fallback in self.fallbacks:
            gateway = find_gateway(
                fallback.get("provider_name"),
                fallback.get("api_key"),
                fallback.get("api_base"),
            )
            self._fallback_gateways.append(gateway)

        # Configure environment variables for primary
        if api_key:
            self._setup_env(api_key, api_base, default_model)

        # NEW: Setup env for all fallbacks
        for fallback in self.fallbacks:
            if fallback.get("api_key"):
                self._setup_fallback_env(
                    fallback.get("api_key"),
                    fallback.get("api_base"),
                    fallback.get("model") or default_model,
                    fallback.get("provider_name"),
                    )

        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _setup_fallback_env(
            self,
            api_key: str,
            api_base: str | None,
            model: str,
            provider_name: str | None,
    ) -> None:
        """Set environment variables for fallback provider."""
        gateway = find_gateway(provider_name, api_key, api_base)
        spec = gateway or find_by_model(model)
        if not spec:
            return

        # Always set fallback env (don't check if already exists)
        os.environ[spec.env_key] = api_key

        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _resolve_model(
            self,
            model: str,
            fallback_index: int | None = None,
    ) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if fallback_index is not None:
            # Use fallback gateway
            gateway = self._fallback_gateways[fallback_index]
        else:
            # Use primary gateway
            gateway = self._gateway

        if gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = gateway.litellm_prefix
            if gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    async def _try_completion(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None,
            model: str,
            max_tokens: int,
            temperature: float,
            fallback_index: int | None = None,
    ) -> LLMResponse:
        """
        Internal method to attempt a completion request.

        Args:
            fallback_index: If None, use primary. Otherwise, use fallback at that index.
        """
        resolved_model = self._resolve_model(model, fallback_index=fallback_index)

        # Clamp max_tokens to at least 1
        max_tokens = max(1, max_tokens)

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Apply model-specific overrides
        self._apply_model_overrides(resolved_model, kwargs)

        # Use fallback credentials if in fallback mode
        if fallback_index is not None:
            fallback = self.fallbacks[fallback_index]
            if fallback.get("api_key"):
                kwargs["api_key"] = fallback["api_key"]
            if fallback.get("api_base"):
                kwargs["api_base"] = fallback["api_base"]
            if fallback.get("extra_headers"):
                kwargs["extra_headers"] = fallback["extra_headers"]
        else:
            # Primary provider
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["api_base"] = self.api_base
            if self.extra_headers:
                kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await acompletion(**kwargs)
        return self._parse_response(response)

    async def chat(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
            model: str | None = None,
            max_tokens: int = 4096,
            temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM with automatic fallback chain.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = model or self.default_model
        errors = []

        # Try primary provider first
        try:
            return await self._try_completion(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                fallback_index=None,
            )
        except Exception as primary_error:
            errors.append(f"Primary ({self.provider_name}/{model}): {str(primary_error)}")
            print(f"⚠️  Primary provider failed: {str(primary_error)}")

        # Try each fallback in order
        for idx, fallback in enumerate(self.fallbacks):
            fallback_model = fallback.get("model", model)
            fallback_provider = fallback.get("provider_name", f"fallback-{idx}")

            print(f"🔄 Trying fallback {idx + 1}/{len(self.fallbacks)}: {fallback_provider}/{fallback_model}...")

            try:
                response = await self._try_completion(
                    messages=messages,
                    tools=tools,
                    model=fallback_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    fallback_index=idx,
                )
                print(f"✅ Fallback {idx + 1} succeeded!")
                return response
            except Exception as fallback_error:
                error_msg = f"Fallback {idx + 1} ({fallback_provider}/{fallback_model}): {str(fallback_error)}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
                continue

        # All providers failed
        error_summary = "\n".join([f"  - {err}" for err in errors])
        return LLMResponse(
            content=f"All providers failed:\n{error_summary}",
            finish_reason="error",
        )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None)

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model