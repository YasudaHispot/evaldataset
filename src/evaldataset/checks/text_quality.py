"""Text quality checks: text length, language, HTML, and mojibake validation."""

from __future__ import annotations

import logging

from datasets import Dataset
from fast_langdetect import detect

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity
from evaldataset.utils.text import count_html_tags, has_mojibake

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


HTML_TAG_THRESHOLD = 5


@register
class HTMLChecker(BaseChecker):
    """Detect texts containing excessive HTML tags."""

    name = "html"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)
        html_indices: list[int] = []

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                continue

            tag_count = count_html_tags(value)
            if tag_count >= HTML_TAG_THRESHOLD:
                html_indices.append(i)

        if html_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(html_indices)} rows with {HTML_TAG_THRESHOLD} or "
                        f"more HTML tags"
                    ),
                    row_indices=html_indices,
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "html_detected_count": len(html_indices),
        }
        return result


@register
class MojibakeChecker(BaseChecker):
    """Detect texts containing mojibake (garbled characters)."""

    name = "mojibake"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)
        mojibake_indices: list[int] = []

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                continue

            try:
                if has_mojibake(value):
                    mojibake_indices.append(i)
            except Exception:
                logger.debug("Mojibake detection failed for row %d, skipping", i)
                continue

        if mojibake_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(mojibake_indices)} rows with suspected "
                        f"mojibake (garbled characters)"
                    ),
                    row_indices=mojibake_indices,
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "mojibake_count": len(mojibake_indices),
        }
        return result
