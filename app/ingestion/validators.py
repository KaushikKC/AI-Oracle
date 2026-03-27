from datetime import datetime, timezone
from typing import Any, Dict


def validate_and_clamp(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce and clamp raw dict fields to satisfy Event domain constraints.
    Mutates a copy; never raises on bad values — instead fixes or falls back.
    """
    out = dict(raw)

    # --- sentiment ---
    try:
        sentiment = float(out.get("sentiment", 0.0))
        out["sentiment"] = max(-1.0, min(1.0, sentiment))
    except (TypeError, ValueError):
        out["sentiment"] = 0.0

    # --- importance_score ---
    try:
        importance = float(out.get("importance_score", 0.5))
        out["importance_score"] = max(0.0, min(1.0, importance))
    except (TypeError, ValueError):
        out["importance_score"] = 0.5

    # --- category ---
    from app.models.event import EventCategory

    valid_categories = {c.value for c in EventCategory}
    raw_cat = str(out.get("category", "other")).strip().lower()
    out["category"] = raw_cat if raw_cat in valid_categories else "other"

    # --- timestamp ---
    ts = out.get("timestamp")
    if isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            out["timestamp"] = parsed
        except ValueError:
            out["timestamp"] = datetime.now(timezone.utc)
    elif isinstance(ts, datetime):
        if ts.tzinfo is None:
            out["timestamp"] = ts.replace(tzinfo=timezone.utc)
    elif ts is None:
        out["timestamp"] = datetime.now(timezone.utc)

    return out
