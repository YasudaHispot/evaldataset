"""Text utility functions."""

from __future__ import annotations

import re

import regex

# Patterns
HTML_TAG_PATTERN = re.compile(r"(?<!\.)</?[a-zA-Z][^>]*>|<!--.*?-->")
CONTROL_CHAR_PATTERN = regex.compile(r"[\p{Cc}&&[^\t\n\r]]", regex.V1)
EXCESSIVE_WHITESPACE_PATTERN = re.compile(r"[ \t]{3,}")
EXCESSIVE_NEWLINE_PATTERN = re.compile(r"\n{4,}")
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+"
)
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)


def count_html_tags(text: str) -> int:
    return len(HTML_TAG_PATTERN.findall(text))


def count_control_chars(text: str) -> int:
    return len(CONTROL_CHAR_PATTERN.findall(text))


def has_excessive_whitespace(text: str) -> bool:
    return bool(EXCESSIVE_WHITESPACE_PATTERN.search(text)) or bool(
        EXCESSIVE_NEWLINE_PATTERN.search(text)
    )


def url_density(text: str) -> float:
    if not text:
        return 0.0
    urls = URL_PATTERN.findall(text)
    url_chars = sum(len(u) for u in urls)
    return url_chars / len(text)


def email_density(text: str) -> float:
    if not text:
        return 0.0
    emails = EMAIL_PATTERN.findall(text)
    email_chars = sum(len(e) for e in emails)
    return email_chars / len(text)


def has_mojibake(text: str) -> bool:
    """Check if text likely contains mojibake (garbled characters)."""
    import ftfy

    fixed = ftfy.fix_text(text)
    return fixed != text
