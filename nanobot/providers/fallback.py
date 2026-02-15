"""Fallback provider: try multiple LLM endpoints in order on failure."""

from dataclasses import dataclass
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse


@dataclass
class _Endpoint:
    """One endpoint in the fallback chain."""
    provider: LLMProvider
    provider_name: str  # For logging (e.g. "vllm", "openrouter")
    model: str
    temperature: float
    max_tokens: int


def _is_error_response(response: LLMResponse) -> bool:
    """True if the response indicates an API/LLM error (should try next provider)."""
    if response.finish_reason == "error":
        return True
    if response.content and response.content.strip().startswith("Error calling LLM:"):
        return True
    return False


class FallbackProvider(LLMProvider):
    """
    Wraps multiple LLM providers and tries them in order.
    On error (finish_reason=="error" or "Error calling LLM:" content), tries the next.
    Logs when falling back to a different provider.
    """

    def __init__(self, endpoints: list[_Endpoint]):
        super().__init__(api_key=None, api_base=None)
        self._endpoints = endpoints
        if not endpoints:
            raise ValueError("FallbackProvider requires at least one endpoint")

    def get_default_model(self) -> str:
        """Return the first endpoint's model."""
        return self._endpoints[0].model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Try each endpoint in order; on error, log and try next."""
        last_response: LLMResponse | None = None
        for i, ep in enumerate(self._endpoints):
            try:
                response = await ep.provider.chat(
                    messages=messages,
                    tools=tools,
                    model=ep.model,
                    max_tokens=ep.max_tokens,
                    temperature=ep.temperature,
                )
                if _is_error_response(response):
                    last_response = response
                    err_preview = (response.content or "")[:200]
                    if i < len(self._endpoints) - 1:
                        next_ep = self._endpoints[i + 1]
                        logger.warning(
                            "Provider {} failed ({}), falling back to {}",
                            ep.provider_name,
                            err_preview,
                            next_ep.provider_name,
                        )
                        continue
                    # Last endpoint failed; return the error
                    return response
                if i > 0:
                    logger.info(
                        "Using provider {} (fallback succeeded)",
                        ep.provider_name,
                    )
                return response
            except Exception as e:
                last_response = LLMResponse(
                    content=f"Error calling LLM: {e!s}",
                    finish_reason="error",
                )
                if i < len(self._endpoints) - 1:
                    next_ep = self._endpoints[i + 1]
                    logger.warning(
                        "Provider {} raised exception ({}), falling back to {}",
                        ep.provider_name,
                        str(e)[:200],
                        next_ep.provider_name,
                    )
                    continue
                return last_response

        return last_response or LLMResponse(
            content="Error calling LLM: no endpoints succeeded",
            finish_reason="error",
        )
