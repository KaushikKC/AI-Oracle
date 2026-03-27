import pytest

from app.ingestion.parsers.structured_parser import StructuredParser


@pytest.fixture
def parser() -> StructuredParser:
    return StructuredParser()


# ── JSON ─────────────────────────────────────────────────────────────────────

def test_json_parser_valid_input_returns_events(parser, sample_structured_json):
    # 2 valid rows, 1 missing description
    events, errors = parser.parse_json(sample_structured_json)
    assert len(events) == 2
    assert len(errors) == 1


def test_json_parser_all_valid(parser):
    rows = [
        {
            "timestamp": "2024-05-01T08:00:00",
            "category": "skills",
            "sentiment": "0.6",
            "importance_score": "0.5",
            "description": "Finished online course.",
        }
    ]
    events, errors = parser.parse_json(rows)
    assert len(events) == 1
    assert errors == []


def test_json_parser_missing_required_field_is_collected_as_error(parser):
    rows = [{"category": "career", "sentiment": "0.5", "importance_score": "0.5"}]
    events, errors = parser.parse_json(rows)
    assert events == []
    assert len(errors) == 1
    assert "Row 0" in errors[0]


def test_json_parser_empty_list(parser):
    events, errors = parser.parse_json([])
    assert events == []
    assert errors == []


def test_json_parser_unknown_category_coerced_to_other(parser):
    rows = [
        {
            "timestamp": "2024-05-01T08:00:00",
            "category": "SPORTS",
            "sentiment": "0.4",
            "importance_score": "0.3",
            "description": "Played basketball.",
        }
    ]
    events, errors = parser.parse_json(rows)
    assert len(events) == 1
    assert events[0].category.value == "other"


# ── CSV ──────────────────────────────────────────────────────────────────────

def test_csv_parser_valid_rows(parser, sample_csv_string):
    # Row 2 has INVALID_CAT → coerced to other (still valid)
    # Row 3 has sentiment=1.9 → clamped to 1.0 (still valid)
    events, errors = parser.parse_csv(sample_csv_string)
    assert len(events) == 3
    assert errors == []


def test_csv_parser_category_coerced(parser, sample_csv_string):
    events, _ = parser.parse_csv(sample_csv_string)
    assert events[1].category.value == "other"


def test_csv_parser_sentiment_clamped(parser, sample_csv_string):
    events, _ = parser.parse_csv(sample_csv_string)
    assert events[2].sentiment == 1.0


def test_csv_parser_extra_columns_are_ignored(parser):
    csv_text = (
        "timestamp,category,sentiment,importance_score,description,extra_field\n"
        "2024-01-10T08:00:00,career,0.5,0.7,Did something important.,ignore_me\n"
    )
    events, errors = parser.parse_csv(csv_text)
    assert len(events) == 1
    assert errors == []


def test_csv_parser_empty_csv(parser):
    events, errors = parser.parse_csv("timestamp,category,sentiment,importance_score,description\n")
    assert events == []
    assert errors == []
