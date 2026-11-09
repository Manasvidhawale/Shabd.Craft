"""
Shabd.Craft — Base LLM Provider Interface

Abstract interface that all providers must implement.
Enables swapping between demo and real providers with minimal code changes.
"""

from abc import ABC, abstractmethod
from src.schemas import LLMRequest, LLMResponse


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        ...

    @property
    @abstractmethod
    def is_demo(self) -> bool:
        """Whether this provider returns simulated responses."""
        ...

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is currently available."""
        ...
