from abc import ABC, abstractmethod

from app.config import settings


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw text completion (expected to be JSON)."""


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "openai":
        from app.llm.openai_client import OpenAIClient
        return OpenAIClient()
    from app.llm.ollama_client import OllamaClient
    return OllamaClient()
