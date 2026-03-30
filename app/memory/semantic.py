"""
Semantic Memory — LLM-extracted behavioral patterns from a set of events.

What "semantic" means here:
  Semantic memory stores general knowledge and patterns — not "what happened"
  but "what is consistently true about this person."
  Example output: "Consistently pursues career growth during periods of high sentiment."

How it works:
  1. Receive a list of events (usually the output of EpisodicMemory.query).
  2. Format them into a prompt with event IDs, timestamps, category, sentiment.
  3. Ask the LLM to identify recurring patterns and return structured JSON.
  4. Parse the JSON into SemanticPattern objects.

Why the LLM is the right tool here (not clustering/ML):
  Patterns like "avoids risk when finances are stressed" require reasoning about
  the meaning of event content, not just numeric similarity. LLMs can cross-reference
  multiple events and infer causal or temporal relationships. For Phase 3 (simulation),
  these patterns become behavioral priors.

Prompt design:
  - System prompt instructs the LLM to respond with raw JSON only (no prose).
  - User prompt provides numbered events with metadata visible (so the LLM can
    reference event_ids and explain which events support each pattern).
  - Returns [] on any parse failure rather than raising — callers get a degraded
    but still valid MemoryResult.
"""

from __future__ import annotations

import json
from typing import List

from app.llm.client import LLMClient, get_llm_client
from app.models.event import Event
from app.models.memory import SemanticPattern


_SYSTEM_PROMPT = (
    "You are an analytical system that identifies recurring behavioral patterns "
    "and tendencies from a person's life events. "
    "Be concise, specific, and evidence-based. "
    "Always respond with valid JSON only — no prose, no markdown."
)


def _build_prompt(events: List[Event]) -> str:
    lines = []
    for e in events:
        lines.append(
            f"- id={e.id} [{e.category.value}] {e.timestamp.date()} "
            f"sentiment={e.sentiment:+.2f} importance={e.importance_score:.2f} "
            f"— {e.description}"
        )
    events_block = "\n".join(lines)
    return (
        f"Analyze these {len(events)} life events and identify recurring patterns "
        f"or behavioral tendencies:\n\n{events_block}\n\n"
        'Return a JSON array:\n'
        '[{"pattern": "...", "supporting_event_ids": [1, 3], "confidence": 0.85}]\n'
        "Return [] if no clear patterns emerge. No explanation outside the JSON."
    )


class SemanticMemory:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or get_llm_client()

    def extract_patterns(self, events: List[Event]) -> List[SemanticPattern]:
        """
        Ask the LLM to identify recurring patterns across the given events.

        Returns an empty list if:
        - events is empty
        - LLM returns unparseable output
        - No patterns are found
        """
        if not events:
            return []
        raw = self._llm.complete(_SYSTEM_PROMPT, _build_prompt(events))
        return _parse_patterns(raw)


def _parse_patterns(raw: str) -> List[SemanticPattern]:
    text = raw.strip()

    # Strip markdown code fences if the LLM wraps its output
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(items, list):
        return []

    patterns: List[SemanticPattern] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            patterns.append(
                SemanticPattern(
                    pattern=str(item["pattern"]),
                    supporting_event_ids=[int(x) for x in item.get("supporting_event_ids", [])],
                    confidence=float(item.get("confidence", 0.5)),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return patterns
