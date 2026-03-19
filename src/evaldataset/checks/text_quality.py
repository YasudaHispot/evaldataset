"""Text quality checks: text length validation."""

from __future__ import annotations

from datasets import Dataset

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity


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
