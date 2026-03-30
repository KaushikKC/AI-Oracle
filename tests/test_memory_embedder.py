"""
Tests for app/memory/embedder.py

What we're testing:
  - OllamaEmbedder calls the right Ollama endpoint and parses the response.
  - OpenAIEmbedder calls the OpenAI SDK and returns the embedding vector.
  - get_embedder() returns OllamaEmbedder by default, OpenAIEmbedder when configured.

We mock httpx and the OpenAI SDK so these tests never make real network calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.memory.embedder import OllamaEmbedder, OpenAIEmbedder, get_embedder


# ── OllamaEmbedder ───────────────────────────────────────────────────────────

class TestOllamaEmbedder:
    def test_calls_correct_endpoint(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.memory.embedder.httpx.post", return_value=mock_response) as mock_post:
            embedder = OllamaEmbedder(base_url="http://localhost:11434", model="nomic-embed-text")
            result = embedder.embed("test text")

        mock_post.assert_called_once_with(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": "test text"},
            timeout=30.0,
        )
        assert result == [0.1, 0.2, 0.3]

    def test_strips_trailing_slash_from_base_url(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [1.0]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.memory.embedder.httpx.post", return_value=mock_response) as mock_post:
            embedder = OllamaEmbedder(base_url="http://localhost:11434/", model="nomic-embed-text")
            embedder.embed("x")

        called_url = mock_post.call_args[0][0]
        assert not called_url.endswith("//api/embeddings"), "double slash in URL"
        assert called_url == "http://localhost:11434/api/embeddings"

    def test_returns_list_of_floats(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.5, -0.3, 0.9]}
        mock_response.raise_for_status = MagicMock()

        with patch("app.memory.embedder.httpx.post", return_value=mock_response):
            embedder = OllamaEmbedder(base_url="http://localhost:11434", model="nomic-embed-text")
            result = embedder.embed("anything")

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)


# ── OpenAIEmbedder ───────────────────────────────────────────────────────────

class TestOpenAIEmbedder:
    def test_calls_openai_sdk(self):
        mock_client = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.4, 0.5, 0.6]
        mock_client.embeddings.create.return_value = MagicMock(data=[embedding_data])

        with patch("app.memory.embedder.OpenAI", return_value=mock_client):
            embedder = OpenAIEmbedder(model="text-embedding-3-small")
            result = embedder.embed("hello world")

        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="hello world",
        )
        assert result == [0.4, 0.5, 0.6]


# ── get_embedder factory ─────────────────────────────────────────────────────

class TestGetEmbedder:
    def test_returns_ollama_by_default(self):
        with patch("app.memory.embedder.settings") as mock_settings:
            mock_settings.embed_provider = "ollama"
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.embed_model = "nomic-embed-text"
            embedder = get_embedder()
        assert isinstance(embedder, OllamaEmbedder)

    def test_returns_openai_when_configured(self):
        with patch("app.memory.embedder.settings") as mock_settings:
            mock_settings.embed_provider = "openai"
            mock_settings.openai_api_key = "sk-test"
            mock_settings.embed_model = "text-embedding-3-small"
            with patch("app.memory.embedder.OpenAI"):
                embedder = get_embedder()
        assert isinstance(embedder, OpenAIEmbedder)
