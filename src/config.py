"""
Shabd.Craft — Configuration Management

Loads settings from environment variables and .env files.
Never exposes API keys in logs, UI, or database.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self._reload()

    def _reload(self):
        """Reload settings from environment."""
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")

        # Automatically adopt GROQ_API_KEY if OPENAI_API_KEY is not set
        if not self.openai_api_key and self.groq_api_key:
            self.openai_api_key = self.groq_api_key

        raw_def_model = os.getenv("SHABDCRAFT_DEFAULT_MODEL", "").strip()
        if self.openai_api_key.startswith("gsk_"):
            self.default_model = "openai/gpt-oss-20b" if (not raw_def_model or raw_def_model.startswith("gpt-")) else raw_def_model
        else:
            self.default_model = raw_def_model or "gpt-3.5-turbo"
        self.demo_mode: bool = os.getenv("SHABDCRAFT_DEMO_MODE", "false").lower() == "true"
        self.db_path: str = os.getenv("SHABDCRAFT_DB_PATH", str(_PROJECT_ROOT / "data" / "shabdcraft.db"))
        self.max_test_cases: int = int(os.getenv("SHABDCRAFT_MAX_TEST_CASES", "50"))
        self.max_optimization_rounds: int = int(os.getenv("SHABDCRAFT_MAX_OPTIMIZATION_ROUNDS", "5"))
        self.max_retries: int = int(os.getenv("SHABDCRAFT_MAX_RETRIES", "3"))
        self.timeout: int = int(os.getenv("SHABDCRAFT_TIMEOUT", "60"))

    @property
    def is_groq(self) -> bool:
        """Check if current active key is a Groq API key."""
        return bool(self.openai_api_key) and self.openai_api_key.startswith("gsk_")

    @property
    def has_api_key(self) -> bool:
        """Check if a real API key is configured."""
        return bool(self.openai_api_key) and self.openai_api_key != "your_openai_api_key_here"

    @property
    def is_demo_mode(self) -> bool:
        """Determine if the app should run in demo mode."""
        return self.demo_mode or not self.has_api_key

    @property
    def active_provider(self) -> str:
        """Return the active provider name."""
        if self.is_demo_mode:
            return "demo"
        return "groq" if self.is_groq else "openai"

    @property
    def active_model(self) -> str:
        """Return the active model name."""
        return "demo-simulator" if self.is_demo_mode else self.default_model

    # Default evaluation weights
    DEFAULT_EVAL_WEIGHTS = {
        "accuracy": 0.25,
        "relevance": 0.20,
        "instruction_adherence": 0.25,
        "clarity": 0.15,
        "format_compliance": 0.15,
    }

    # Default generation settings
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 1024

    # Available models
    AVAILABLE_MODELS = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-4o-mini",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]

    # Pricing per 1K tokens (approximate, for cost estimation only)
    MODEL_PRICING = {
        "openai/gpt-oss-20b": {"input": 0.0001, "output": 0.0001},
        "openai/gpt-oss-120b": {"input": 0.0002, "output": 0.0002},
        "qwen/qwen3.8-27b": {"input": 0.0001, "output": 0.0001},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
        "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
        "mixtral-8x7b-32768": {"input": 0.00024, "output": 0.00024},
    }


    # Maximum context window (in tokens) per model
    MODEL_CONTEXT_WINDOWS = {
        "openai/gpt-oss-20b": 131072,
        "openai/gpt-oss-120b": 131072,
        "qwen/qwen3.8-27b": 32768,
        "gpt-3.5-turbo": 16385,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "llama-3.3-70b-versatile": 128000,
        "llama-3.1-8b-instant": 128000,
        "mixtral-8x7b-32768": 32768,
    }


# Singleton settings instance
settings = Settings()
