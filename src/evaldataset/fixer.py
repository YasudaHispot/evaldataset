"""Text cleaner (auto-fixer) for dataset quality issues.

Applies a pipeline of fixes to text fields:
1. Mojibake repair (ftfy)
2. HTML tag removal (BeautifulSoup)
3. Control character removal (regex)
4. Excessive whitespace normalization (regex)
"""

from __future__ import annotations

import logging
from typing import Any

import regex
import ftfy
from bs4 import BeautifulSoup
from datasets import Dataset

from evaldataset.utils.text import (
    EXCESSIVE_NEWLINE_PATTERN,
    EXCESSIVE_WHITESPACE_PATTERN,
)

# Control-character pattern compiled with V1 flag so that the set-
# intersection syntax ``[\p{Cc}&&[^\t\n\r]]`` works correctly.
_CONTROL_CHAR_RE = regex.compile(r"[\p{Cc}&&[^\t\n\r]]", regex.V1)

logger = logging.getLogger(__name__)


class TextCleaner:
    """Clean and normalize text fields in a HuggingFace Dataset.

    The fix pipeline is applied in order:
    1. Mojibake repair via ``ftfy.fix_text``
    2. HTML tag stripping via ``BeautifulSoup.get_text``
    3. Control character removal (preserving ``\\t``, ``\\n``, ``\\r``)
    4. Excessive whitespace / newline normalization and strip
    """

    # ------------------------------------------------------------------
    # Single-text pipeline
    # ------------------------------------------------------------------

    def fix_text(self, text: str | None) -> str | None:
        """Apply the full cleaning pipeline to a single string.

        Parameters
        ----------
        text:
            Raw text that may contain mojibake, HTML tags, control
            characters, or excessive whitespace.  ``None`` is accepted
            and returned as-is.

        Returns
        -------
        str | None
            Cleaned text, or ``None`` if the input was ``None``.
        """
        if text is None:
            return None
        # Step 1: mojibake repair
        text = self._fix_mojibake(text)
        # Step 2: HTML tag removal
        text = self._strip_html(text)
        # Step 3: control character removal
        text = self._remove_control_chars(text)
        # Step 4: whitespace normalization
        text = self._normalize_whitespace(text)
        return text

    # ------------------------------------------------------------------
    # Dataset-level pipeline
    # ------------------------------------------------------------------

    def fix_dataset(
        self, dataset: Dataset, text_field: str
    ) -> tuple[Dataset, dict[str, Any]]:
        """Apply the cleaning pipeline to every row of *dataset*.

        Parameters
        ----------
        dataset:
            A HuggingFace ``Dataset`` instance.
        text_field:
            Name of the column containing the text to clean.

        Returns
        -------
        tuple[Dataset, dict[str, Any]]
            A 2-tuple of (cleaned_dataset, stats).  ``stats`` records
            how many rows were affected at each pipeline step and in
            total.
        """
        stats: dict[str, Any] = {
            "total_rows": len(dataset),
            "mojibake_fixed": 0,
            "html_stripped": 0,
            "control_chars_removed": 0,
            "whitespace_normalized": 0,
            "fixed_count": 0,
            "total_fixed": 0,
        }

        def _apply_pipeline(row: dict[str, Any]) -> dict[str, Any]:
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                return row

            original = value
            current = value

            # Step 1: mojibake
            after_mojibake = self._fix_mojibake(current)
            if after_mojibake != current:
                stats["mojibake_fixed"] += 1
            current = after_mojibake

            # Step 2: HTML
            after_html = self._strip_html(current)
            if after_html != current:
                stats["html_stripped"] += 1
            current = after_html

            # Step 3: control chars
            after_ctrl = self._remove_control_chars(current)
            if after_ctrl != current:
                stats["control_chars_removed"] += 1
            current = after_ctrl

            # Step 4: whitespace
            after_ws = self._normalize_whitespace(current)
            if after_ws != current:
                stats["whitespace_normalized"] += 1
            current = after_ws

            if current != original:
                stats["fixed_count"] += 1
                stats["total_fixed"] += 1

            row = dict(row)
            row[text_field] = current
            return row

        cleaned = dataset.map(_apply_pipeline)
        return cleaned, stats

    # ------------------------------------------------------------------
    # Individual pipeline steps (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_mojibake(text: str) -> str:
        """Repair mojibake / encoding errors using ftfy."""
        return ftfy.fix_text(text)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags, returning plain text content."""
        soup = BeautifulSoup(text, "html.parser")
        # Remove <script> and <style> tags entirely
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text()

    @staticmethod
    def _remove_control_chars(text: str) -> str:
        """Remove control characters except ``\\t``, ``\\n``, ``\\r``."""
        return _CONTROL_CHAR_RE.sub("", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Collapse excessive whitespace / newlines and strip edges."""
        text = EXCESSIVE_WHITESPACE_PATTERN.sub("  ", text)
        text = EXCESSIVE_NEWLINE_PATTERN.sub("\n\n\n", text)
        return text.strip()
