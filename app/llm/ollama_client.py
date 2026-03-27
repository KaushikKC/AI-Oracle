import httpx

from app.config import settings
from app.llm.client import LLMClient


class OllamaClient(LLMClient):
    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
