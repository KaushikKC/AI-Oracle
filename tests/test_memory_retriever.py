"""
Tests for app/memory/retriever.py

What we're testing:
  - parse_time_window() correctly extracts days from natural-language phrases.
  - query() returns a MemoryResult with the right structure.
  - Time window in query → temporal field is populated; no time phrase → temporal is None.
  - include_semantic=False skips pattern extraction.
  - Episodic results are present when the store has data.
  - Empty store still returns a valid (empty) MemoryResult.
"""

import pytest
from unittest.mock import MagicMock

from app.llm.client import LLMClient
from app.memory.retriever import MemoryRetriever, parse_time_window
from app.models.memory import MemoryResult


# ── Time window parsing ──────────────────────────────────────────────────────

class TestParseTimeWindow:
    @pytest.mark.parametrize("query,expected", [
        ("career decisions in the last year", 365),
        ("what happened last year", 365),
        ("last 30 days", 30),
        ("last 90 days", 90),
        ("last 7 days", 7),
        ("last week", 7),
        ("last month", 30),
        ("last quarter", 90),
        ("Last Year",  365),      # case insensitive
        ("show me last 180 days of health events", 180),
    ])
    def test_parses_correctly(self, query, expected):
        assert parse_time_window(query) == expected

    @pytest.mark.parametrize("query", [
        "career decisions",
        "how am I doing",
        "finances",
        "",
    ])
    def test_returns_none_when_no_time_phrase(self, query):
        assert parse_time_window(query) is None


# ── MemoryRetriever ───────────────────────────────────────────────────────────

class TestMemoryRetriever:
    def test_returns_memory_result(self, populated_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career achievements")
        assert isinstance(result, MemoryResult)
        assert result.query == "career achievements"

    def test_episodic_results_present(self, populated_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career", include_semantic=False)
        assert len(result.episodic) > 0

    def test_no_time_phrase_gives_no_temporal(self, populated_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career achievements", include_semantic=False)
        assert result.temporal is None

    def test_time_phrase_gives_temporal_window(self, populated_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career decisions in the last year", include_semantic=False)
        assert result.temporal is not None
        assert result.temporal.window_days == 365

    def test_include_semantic_false_skips_llm(self, populated_store, mock_embedder):
        mock_llm = MagicMock(spec=LLMClient)
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm,
        )
        result = retriever.query("anything", include_semantic=False)
        mock_llm.complete.assert_not_called()
        assert result.semantic == []

    def test_include_semantic_true_calls_llm(self, populated_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career", include_semantic=True)
        mock_llm_for_patterns.complete.assert_called_once()
        assert len(result.semantic) > 0

    def test_empty_store_returns_empty_result(self, vector_store, mock_embedder, mock_llm_for_patterns):
        retriever = MemoryRetriever(
            store=vector_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career", include_semantic=False)
        assert result.episodic == []
        assert result.semantic == []

    def test_testable_output_career_last_year(self, populated_store, mock_embedder, mock_llm_for_patterns):
        """
        The spec's testable output: 'career decisions in the last year'
        → ranked time-ordered events with relevance scores.
        """
        retriever = MemoryRetriever(
            store=populated_store,
            embedder=mock_embedder,
            llm_client=mock_llm_for_patterns,
        )
        result = retriever.query("career decisions in the last year", include_semantic=False)

        # Temporal window present with 365 days
        assert result.temporal is not None
        assert result.temporal.window_days == 365

        # Temporal events are time-ordered
        times = [e.timestamp for e in result.temporal.events]
        assert times == sorted(times)

        # Episodic results have relevance scores
        for r in result.episodic:
            assert 0.0 <= r.relevance_score <= 1.0
