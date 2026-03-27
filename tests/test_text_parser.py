import json
from unittest.mock import MagicMock

import pytest

from app.ingestion.parsers.text_parser import TextParser
from app.llm.client import LLMClient


@pytest.fixture
def parser(mock_llm_client) -> TextParser:
    return TextParser(mock_llm_client)


def test_text_parser_calls_llm_with_correct_prompt(parser, mock_llm_client, sample_journal_text):
    parser.parse_text(sample_journal_text)
    assert mock_llm_client.complete.called
    call_args = mock_llm_client.complete.call_args
    user_prompt = call_args[0][1]
    assert sample_journal_text in user_prompt


def test_text_parser_parses_valid_llm_json_response(parser, sample_journal_text):
    events, errors = parser.parse_text(sample_journal_text)
    assert len(events) == 2
    assert errors == []
    assert events[0].category.value == "career"
    assert events[1].category.value == "health"


def test_text_parser_handles_llm_returning_prose(mock_llm_client):
    mock_llm_client.complete.return_value = "Sorry, I cannot help with that."
    parser = TextParser(mock_llm_client)
    events, errors = parser.parse_text("Some journal text.")
    assert events == []
    assert len(errors) == 1
    assert "non-JSON" in errors[0]


def test_text_parser_strips_markdown_code_fences(mock_llm_client):
    raw = '[{"timestamp":"2024-01-01T10:00:00","category":"career","sentiment":0.5,"importance_score":0.5,"description":"Did a thing."}]'
    mock_llm_client.complete.return_value = f"```json\n{raw}\n```"
    parser = TextParser(mock_llm_client)
    events, errors = parser.parse_text("test")
    assert len(events) == 1
    assert errors == []


def test_text_parser_handles_partial_valid_json(mock_llm_client):
    # Second item is missing description → error collected, first item passes
    response = json.dumps([
        {"timestamp": "2024-01-01T10:00:00", "category": "career", "sentiment": 0.5, "importance_score": 0.5, "description": "Good day."},
        {"timestamp": "2024-01-02T10:00:00", "category": "health", "sentiment": -0.2, "importance_score": 0.3},
    ])
    mock_llm_client.complete.return_value = response
    parser = TextParser(mock_llm_client)
    events, errors = parser.parse_text("test")
    assert len(events) == 1
    assert len(errors) == 1


def test_text_parser_handles_llm_failure(mock_llm_client):
    mock_llm_client.complete.side_effect = ConnectionError("Ollama not running")
    parser = TextParser(mock_llm_client)
    events, errors = parser.parse_text("journal text")
    assert events == []
    assert len(errors) == 1
    assert "LLM call failed" in errors[0]


def test_text_parser_returns_empty_for_empty_llm_array(mock_llm_client):
    mock_llm_client.complete.return_value = "[]"
    parser = TextParser(mock_llm_client)
    events, errors = parser.parse_text("nothing relevant happened")
    assert events == []
    assert errors == []
