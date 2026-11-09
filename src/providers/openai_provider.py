"""
Shabd.Craft — OpenAI LLM Provider

Real provider using the official OpenAI Python SDK.
Never logs or exposes API keys.
"""

from __future__ import annotations

import time
from typing import Optional

from src.providers.base import BaseLLMProvider
from src.schemas import LLMRequest, LLMResponse
from src.config import settings


class OpenAIProvider(BaseLLMProvider):
    """Real OpenAI API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.openai_api_key

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def is_demo(self) -> bool:
        return False

    def is_available(self) -> bool:
        return bool(self._api_key) and self._api_key != "your_openai_api_key_here"

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(
                content="",
                error="OpenAI API key is not configured. Please set OPENAI_API_KEY in your .env file.",
                is_demo=False,
            )

        try:
            import openai

            client = openai.OpenAI(api_key=self._api_key, timeout=settings.timeout)

            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.user_prompt})

            start = time.time()
            response = client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            latency_ms = (time.time() - start) * 1000

            choice = response.choices[0]
            usage = response.usage

            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            # Cost estimation based on known pricing
            cost = self._estimate_cost(request.model, prompt_tokens, completion_tokens)

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=round(latency_ms, 1),
                cost_estimate=cost,
                is_demo=False,
            )

        except openai.AuthenticationError:
            return LLMResponse(
                content="", error="Authentication failed. Please check your OpenAI API key.", is_demo=False,
            )
        except openai.RateLimitError:
            return LLMResponse(
                content="", error="Rate limit exceeded. Please wait and try again.", is_demo=False,
            )
        except openai.APIConnectionError:
            return LLMResponse(
                content="", error="Cannot connect to OpenAI API. Check your internet connection.", is_demo=False,
            )
        except openai.APITimeoutError:
            return LLMResponse(
                content="", error=f"Request timed out after {settings.timeout}s. Try a shorter prompt or increase timeout.", is_demo=False,
            )
        except openai.APIError as e:
            return LLMResponse(
                content="", error=f"OpenAI API error: {type(e).__name__}", is_demo=False,
            )
        except Exception as e:
            return LLMResponse(
                content="", error=f"Unexpected error: {type(e).__name__}", is_demo=False,
            )

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on approximate token pricing."""
        pricing = settings.MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)
