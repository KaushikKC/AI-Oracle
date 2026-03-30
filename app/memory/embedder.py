"""
Embedding layer for Phase 2 Memory System.

Why a separate Embedder (not reuse LLMClient)?
- LLMClient does text completion (prompt → text response).
- Embedders do text → dense vector; completely different API shape,
  different models, different latency profile.
- Keeping them separate lets you swap embedding models without touching
  the generation pipeline, and vice versa.

Two concrete implementations:
  OllamaEmbedder  — calls the Ollama /api/embeddings endpoint.
                    Default model: nomic-embed-text (768-dim, fast, local).
  OpenAIEmbedder  — calls text-embedding-3-small (1536-dim).

Both are selected by the embed_provider setting in config.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import httpx

from app.config import settings

# Lazy module-level import so the name exists for patching in tests,
# but openai doesn't need to be installed if you're using Ollama only.
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]


class Embedder(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return a dense embedding vector for the given text."""


class OllamaEmbedder(Embedder):
    """
    Calls POST {ollama_base_url}/api/embeddings with the configured model.
    Ollama returns {"embedding": [float, ...]}.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.embed_model

    def embed(self, text: str) -> List[float]:
        resp = httpx.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


class OpenAIEmbedder(Embedder):
    """
    Calls the OpenAI embeddings endpoint.
    Default model: text-embedding-3-small (1536-dim, cheap, fast).
    """

    def __init__(self, model: str | None = None) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.embed_model

    def embed(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding


def get_embedder() -> Embedder:
    """Factory: returns the configured embedder (mirrors get_llm_client pattern)."""
    if settings.embed_provider == "openai":
        return OpenAIEmbedder()
    return OllamaEmbedder()
