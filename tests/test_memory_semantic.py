"""
Tests for app/memory/semantic.py

What we're testing:
  - extract_patterns() calls the LLM with all event data.
  - Returns SemanticPattern objects when LLM gives valid JSON.
  - Returns empty list for empty event input.
  - Returns empty list when LLM returns malformed output.
  - Handles LLM wrapping output in markdown code fences.
  - Partial failures in pattern items are skipped gracefully.
"""

from unittest.mock import MagicMock

import pytest

from app.llm.client import LLMClient
from app.memory.semantic import SemanticMemory, _parse_patterns
from app.models.memory import SemanticPattern


VALID_JSON = (
    '[{"pattern": "Shows consistent career growth", '
    '"supporting_event_ids": [1, 2], "confidence": 0.9}]'
)

WITH_CODE_FENCE = f"```json\n{VALID_JSON}\n```"

MULTIPLE_PATTERNS = (
    '[{"pattern": "Career-focused", "supporting_event_ids": [1], "confidence": 0.8},'
    ' {"pattern": "Health neglected under stress", "supporting_event_ids": [3], "confidence": 0.7}]'
)


class TestExtractPatterns:
    def test_returns_patterns_on_valid_response(self, sample_events, mock_llm_for_patterns):
        memory = SemanticMemory(llm_client=mock_llm_for_patterns)
        results = memory.extract_patterns(sample_events)
        assert len(results) == 1
        assert isinstance(results[0], SemanticPattern)
        assert results[0].pattern == "Shows consistent career growth"
        assert results[0].confidence == 0.9

    def test_empty_events_returns_empty_list(self, mock_llm_for_patterns):
        memory = SemanticMemory(llm_client=mock_llm_for_patterns)
        results = memory.extract_patterns([])
        assert results == []
        mock_llm_for_patterns.complete.assert_not_called()

    def test_llm_is_called_with_event_details(self, sample_events, mock_llm_for_patterns):
        memory = SemanticMemory(llm_client=mock_llm_for_patterns)
        memory.extract_patterns(sample_events)
        assert mock_llm_for_patterns.complete.called
        _, user_prompt = mock_llm_for_patterns.complete.call_args[0]
        # Event descriptions should appear in the prompt
        assert "senior engineer" in user_prompt
        assert "product launch" in user_prompt

    def test_multiple_patterns_returned(self, sample_events):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.complete.return_value = MULTIPLE_PATTERNS
        memory = SemanticMemory(llm_client=mock_llm)
        results = memory.extract_patterns(sample_events)
        assert len(results) == 2


class TestParsePatterns:
    def test_valid_json(self):
        patterns = _parse_patterns(VALID_JSON)
        assert len(patterns) == 1
        assert patterns[0].pattern == "Shows consistent career growth"
        assert patterns[0].supporting_event_ids == [1, 2]

    def test_code_fence_stripped(self):
        patterns = _parse_patterns(WITH_CODE_FENCE)
        assert len(patterns) == 1

    def test_malformed_json_returns_empty(self):
        assert _parse_patterns("not json at all") == []

    def test_non_array_returns_empty(self):
        assert _parse_patterns('{"pattern": "x"}') == []

    def test_empty_array_returns_empty(self):
        assert _parse_patterns("[]") == []

    def test_invalid_items_skipped(self):
        mixed = '[{"pattern": "good", "supporting_event_ids": [1], "confidence": 0.7}, "bad_item"]'
        patterns = _parse_patterns(mixed)
        assert len(patterns) == 1
        assert patterns[0].pattern == "good"

    def test_missing_confidence_defaults_to_half(self):
        no_conf = '[{"pattern": "test", "supporting_event_ids": []}]'
        patterns = _parse_patterns(no_conf)
        assert patterns[0].confidence == 0.5

    def test_missing_supporting_ids_defaults_to_empty(self):
        no_ids = '[{"pattern": "test", "confidence": 0.6}]'
        patterns = _parse_patterns(no_ids)
        assert patterns[0].supporting_event_ids == []
