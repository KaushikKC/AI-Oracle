import csv
import io
from typing import List, Tuple

from pydantic import ValidationError

from app.ingestion.parsers.base import BaseParser
from app.ingestion.validators import validate_and_clamp
from app.models.event import Event


class StructuredParser(BaseParser):
    """Parses pre-structured JSON (list of dicts) or CSV text into Events."""

    def parse(self, raw_input: object) -> Tuple[List[Event], List[str]]:
        raise NotImplementedError("Use parse_json or parse_csv directly.")

    def parse_json(self, rows: List[dict]) -> Tuple[List[Event], List[str]]:
        events: List[Event] = []
        errors: List[str] = []
        for i, row in enumerate(rows):
            try:
                raw = dict(row)
                raw["source_raw"] = str(row)
                clamped = validate_and_clamp(raw)
                events.append(Event(**clamped))
            except (ValidationError, Exception) as exc:
                errors.append(f"Row {i}: {exc}")
        return events, errors

    def parse_csv(self, csv_text: str) -> Tuple[List[Event], List[str]]:
        events: List[Event] = []
        errors: List[str] = []
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        for i, row in enumerate(reader):
            try:
                raw = {k.strip(): v.strip() for k, v in row.items() if k}
                raw["source_raw"] = str(dict(row))
                clamped = validate_and_clamp(raw)
                events.append(Event(**clamped))
            except (ValidationError, Exception) as exc:
                errors.append(f"Row {i}: {exc}")
        return events, errors
