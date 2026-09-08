"""
Shared result structure returned by every source module.

Each source's fetch() returns a list[Result] using this exact shape so the
scoring and responder stages can treat all four sources identically.
"""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Result:
    # Populated by the source modules:
    source: str                       # "reddit" | "quora" | "google" | "perplexity"
    title: str
    url: str
    summary: str = ""                 # short human-readable summary
    raw_snippet: str = ""             # fuller raw text pulled from the item
    timestamp: str = ""               # ISO8601 of the item, if known (else "")

    # Populated later by scoring.py:
    result_type: str = ""             # "A" (engagement) | "B" (build signal)
    score: float = 0.0                # ranking score for Type A
    rank: Optional[int] = None        # 1..TOP_N for the daily Type A list
    pattern: str = ""                 # for Type B: the observed pattern/theme

    # Populated later by responder.py (Type A top-N only):
    draft_response: str = ""

    def to_row(self) -> dict:
        return asdict(self)
