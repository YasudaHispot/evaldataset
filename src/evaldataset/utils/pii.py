"""PII detection patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PiiMatch:
    pii_type: str
    value: str
    start: int
    end: int


# Patterns
_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    ),
    "phone_jp": re.compile(r"0\d{1,4}-\d{1,4}-\d{3,4}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
}


def detect_pii(text: str) -> list[PiiMatch]:
    """Detect PII patterns in text."""
    matches: list[PiiMatch] = []
    for pii_type, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            matches.append(
                PiiMatch(
                    pii_type=pii_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                )
            )
    return matches
