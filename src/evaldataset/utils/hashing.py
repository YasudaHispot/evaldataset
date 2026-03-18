"""Hashing utilities for duplicate detection."""

from __future__ import annotations

import hashlib


def sha256_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_to_shingles(text: str, k: int = 5) -> set[str]:
    """Convert text to a set of character k-shingles."""
    words = text.lower().split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}
