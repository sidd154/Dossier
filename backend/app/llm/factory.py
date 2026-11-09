"""Provider selection from configuration."""

from functools import lru_cache

from app.config import get_settings
from app.core.exceptions import AppError
from app.llm.ollama import OllamaProvider
from app.llm.provider import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_chat_model,
            timeout=float(settings.llm_timeout_seconds),
        )
    raise AppError(f"Unsupported LLM provider: {settings.llm_provider}")
