"""Text quality checks: text length and language validation."""

from __future__ import annotations

import logging

from datasets import Dataset
from fast_langdetect import detect

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity

logger = logging.getLogger(__name__)


@register
class TextLengthChecker(BaseChecker):
    """Detect texts shorter than min_length or longer than max_length."""

    name = "text_length"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)
        too_short_indices: list[int] = []
        too_long_indices: list[int] = []

        min_len = self.config.min_length
        max_len = self.config.max_length

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                continue
            text_len = len(value)
            if text_len < min_len:
                too_short_indices.append(i)
            if text_len > max_len:
                too_long_indices.append(i)

        if too_short_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(too_short_indices)} rows with text shorter than "
                        f"{min_len} characters"
                    ),
                    row_indices=too_short_indices,
                )
            )

        if too_long_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(too_long_indices)} rows with text longer than "
                        f"{max_len} characters"
                    ),
                    row_indices=too_long_indices,
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "too_short_count": len(too_short_indices),
            "too_long_count": len(too_long_indices),
            "min_length_threshold": min_len,
            "max_length_threshold": max_len,
        }
        return result


@register
class LanguageChecker(BaseChecker):
    """Detect texts written in languages not in the allowed list."""

    name = "language"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)
        non_target_indices: list[int] = []
        checked_count = 0

        allowed_languages = self.config.languages
        threshold = self.config.language_threshold

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                continue

            try:
                detection = detect(value)
            except Exception:
                logger.debug("Language detection failed for row %d, skipping", i)
                continue

            checked_count += 1

            # detect() returns a list of dicts; use the top prediction
            top = detection[0]
            lang = top["lang"]
            score = top["score"]

            if lang not in allowed_languages and score >= threshold:
                non_target_indices.append(i)

        if non_target_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(non_target_indices)} rows with non-target "
                        f"language (allowed: {allowed_languages})"
                    ),
                    row_indices=non_target_indices,
                )
            )

        result.stats = {
            "checked_count": checked_count,
            "non_target_count": len(non_target_indices),
        }
        return result
