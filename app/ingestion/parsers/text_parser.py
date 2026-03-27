import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.ingestion.parsers.base import BaseParser
from app.ingestion.validators import validate_and_clamp
from app.llm.client import LLMClient
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.models.event import Event


class TextParser(BaseParser):
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def parse(self, raw_input: object) -> Tuple[List[Event], List[str]]:
        raise NotImplementedError("Use parse_text directly.")

    def parse_text(
        self,
        text: str,
        hint_timestamp: Optional[datetime] = None,
    ) -> Tuple[List[Event], List[str]]:
        hint_str = hint_timestamp.isoformat() if hint_timestamp else None
        user_prompt = build_user_prompt(text, hint_str)

        try:
            raw_response = self._llm.complete(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            return [], [f"LLM call failed: {exc}"]

        raw_response = raw_response.strip()

        # Strip markdown code fences if model adds them despite instructions
        if raw_response.startswith("```"):
            lines = raw_response.splitlines()
            raw_response = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        try:
            items = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            return [], [f"LLM returned non-JSON: {exc} | response: {raw_response[:200]}"]

        if not isinstance(items, list):
            return [], [f"LLM returned non-array JSON: {type(items).__name__}"]

        events: List[Event] = []
        errors: List[str] = []

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"Item {i}: expected object, got {type(item).__name__}")
                continue
            try:
                item["source_raw"] = text
                clamped = validate_and_clamp(item)
                events.append(Event(**clamped))
            except Exception as exc:
                errors.append(f"Item {i}: {exc}")

        return events, errors
