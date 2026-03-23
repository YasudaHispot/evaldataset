"""Text cleaner (auto-fixer) and row filter for dataset quality issues.

Applies a pipeline of fixes to text fields:
1. Mojibake repair (ftfy)
2. HTML tag removal (BeautifulSoup)
3. Control character removal (regex)
4. Excessive whitespace normalization (regex)

After cleaning, RowFilter removes problem rows identified by checkers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from copy import copy
from typing import Any

import ftfy
from bs4 import BeautifulSoup
from datasets import Dataset

from evaldataset.models import CheckResult
from evaldataset.utils.hashing import sha256_hash
from evaldataset.utils.text import (
    CONTROL_CHAR_PATTERN,
    EXCESSIVE_NEWLINE_PATTERN,
    EXCESSIVE_WHITESPACE_PATTERN,
)

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
        return CONTROL_CHAR_PATTERN.sub("", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Collapse excessive whitespace / newlines and strip edges."""
        text = EXCESSIVE_WHITESPACE_PATTERN.sub("  ", text)
        text = EXCESSIVE_NEWLINE_PATTERN.sub("\n\n\n", text)
        return text.strip()


class RowFilter:
    """Filter rows based on checker results.

    Removes every row whose index appears in a filter-eligible checker's
    ``Issue.row_indices``.  The caller is responsible for ensuring that
    the ``row_indices`` lists contain only the rows that should actually
    be removed (e.g. for duplicate checkers, the first occurrence of each
    group should already be excluded from ``row_indices``).

    Use :meth:`strip_first_duplicates` to preprocess checker results
    from duplicate checkers before passing them to :meth:`filter_dataset`.

    Intended to run **after** ``TextCleaner`` in the fix pipeline so that
    only issues surviving text cleaning are filtered out.
    """

    # Checker names whose Issue.row_indices drive row removal.
    FILTER_CHECKERS = ["exact_duplicate", "near_duplicate", "text_length", "pii"]

    def filter_dataset(
        self,
        dataset: Dataset,
        check_results: list[CheckResult],
        skip_checkers: list[str] | None = None,
    ) -> tuple[Dataset, dict[str, Any]]:
        """Remove problem rows from *dataset* based on *check_results*.

        Every ``Issue.row_indices`` entry from a filter-eligible checker
        is treated as a row to remove.  Indices that appear in multiple
        checkers are counted once in ``total_rows_removed``.

        Parameters
        ----------
        dataset:
            The (already cleaned) HuggingFace ``Dataset``.
        check_results:
            Output from running checkers on *dataset*.  For duplicate
            checkers, call :meth:`strip_first_duplicates` beforehand so
            that ``row_indices`` contains only the redundant copies.
        text_field:
            Name of the text column.
        skip_checkers:
            Checker names to exclude from filtering (e.g. from
            ``--skip-checker``).

        Returns
        -------
        tuple[Dataset, dict[str, Any]]
            ``(filtered_dataset, filter_stats)`` where *filter_stats*
            records per-checker removal counts and totals.
        """
        skip = set(skip_checkers) if skip_checkers else set()

        # Collect per-checker removal indices
        per_checker_remove: dict[str, set[int]] = {}
        for result in check_results:
            name = result.checker_name
            if name not in self.FILTER_CHECKERS or name in skip:
                continue
            flagged = self._collect_flagged_indices(result)
            if not flagged:
                continue
            per_checker_remove[name] = flagged

        # Union all removal indices
        all_remove: set[int] = set()
        for indices in per_checker_remove.values():
            all_remove |= indices

        # Build filter_stats -- always include all FILTER_CHECKERS keys
        # (skipped checkers report 0 to keep a predictable schema).
        filter_stats: dict[str, Any] = {}
        for checker_name in self.FILTER_CHECKERS:
            if checker_name in skip:
                filter_stats[checker_name] = 0
            else:
                filter_stats[checker_name] = len(
                    per_checker_remove.get(checker_name, set())
                )
        filter_stats["total_rows_removed"] = len(all_remove)
        filter_stats["rows_after_filter"] = len(dataset) - len(all_remove)

        # Apply filter
        if all_remove:
            filtered = dataset.filter(
                lambda _, idx: idx not in all_remove,
                with_indices=True,
            )
        else:
            filtered = dataset

        return filtered, filter_stats

    # ------------------------------------------------------------------
    # Duplicate preprocessing
    # ------------------------------------------------------------------

    @staticmethod
    def strip_first_duplicates(
        dataset: Dataset,
        check_results: list[CheckResult],
        text_field: str = "text",
    ) -> list[CheckResult]:
        """Remove the first occurrence of each duplicate group from results.

        For checkers ``exact_duplicate`` and ``near_duplicate``, the raw
        ``Issue.row_indices`` contain **all** members of each duplicate
        group (including the first occurrence that should be kept).  This
        method returns a copy of *check_results* where, for those two
        checkers, the first (lowest-index) member of each hash-group is
        removed from ``row_indices``.

        Non-duplicate checker results are returned unchanged.

        Parameters
        ----------
        dataset:
            The dataset whose text values are used for grouping.
        check_results:
            The raw checker output.
        text_field:
            Column name containing the text.

        Returns
        -------
        list[CheckResult]
            A shallow copy with adjusted ``row_indices`` for duplicate
            checkers.
        """
        duplicate_checkers = {"exact_duplicate", "near_duplicate"}
        adjusted: list[CheckResult] = []

        for result in check_results:
            if result.checker_name not in duplicate_checkers:
                adjusted.append(result)
                continue

            # Collect all flagged indices across issues
            all_flagged: set[int] = set()
            for issue in result.issues:
                all_flagged.update(issue.row_indices)

            if not all_flagged:
                adjusted.append(result)
                continue

            # Group by text hash, keep the first (lowest index) per group
            hash_to_indices: dict[str, list[int]] = defaultdict(list)
            for idx in sorted(all_flagged):
                row = dataset[int(idx)]
                value = row.get(text_field)
                if value is None or not isinstance(value, str):
                    continue
                h = sha256_hash(value)
                hash_to_indices[h].append(idx)

            keep_indices: set[int] = set()
            for indices in hash_to_indices.values():
                if len(indices) >= 2:
                    keep_indices.add(indices[0])

            # Build adjusted issues (remove kept indices from row_indices)
            new_issues = []
            for issue in result.issues:
                new_row_indices = [
                    idx for idx in issue.row_indices if idx not in keep_indices
                ]
                new_issue = copy(issue)
                new_issue.row_indices = new_row_indices
                new_issues.append(new_issue)

            new_result = CheckResult(
                checker_name=result.checker_name,
                issues=new_issues,
                stats=result.stats,
            )
            adjusted.append(new_result)

            logger.debug(
                "strip_first_duplicates[%s]: flagged=%d, kept=%d, removable=%d",
                result.checker_name,
                len(all_flagged),
                len(keep_indices),
                len(all_flagged) - len(keep_indices),
            )

        return adjusted

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_flagged_indices(result: CheckResult) -> set[int]:
        """Gather all ``row_indices`` from a checker's issues."""
        indices: set[int] = set()
        for issue in result.issues:
            indices.update(issue.row_indices)
        return indices
