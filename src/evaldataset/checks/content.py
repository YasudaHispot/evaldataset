"""Content quality checks: PII detection, token length, boilerplate."""

from __future__ import annotations

from collections import Counter

import tiktoken
from datasets import Dataset

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity
from evaldataset.utils.pii import detect_pii as find_pii


@register
class PiiChecker(BaseChecker):
    """Detect rows containing PII (personally identifiable information)."""

    name = "pii"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)

        # Skip if config says so
        if not self.config.detect_pii:
            result.stats = {"skipped": True}
            return result

        pii_row_indices: list[int] = []
        pii_type_counter: Counter[str] = Counter()
        row_pii_details: list[dict[str, str | int]] = []

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            # Skip None and non-string values
            if value is None or not isinstance(value, str):
                continue

            matches = find_pii(value)
            if matches:
                pii_row_indices.append(i)
                for match in matches:
                    pii_type_counter[match.pii_type] += 1
                    row_pii_details.append(
                        {
                            "row_index": i,
                            "pii_type": match.pii_type,
                        }
                    )

        if pii_row_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(pii_row_indices)} rows containing PII"
                    ),
                    row_indices=pii_row_indices,
                    details={
                        "pii_types": dict(pii_type_counter),
                        "pii_matches": row_pii_details,
                    },
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "pii_detected_count": len(pii_row_indices),
            **{f"pii_{pii_type}_count": count for pii_type, count in pii_type_counter.items()},
        }
        return result


@register
class TokenLengthChecker(BaseChecker):
    """Detect rows where token count exceeds max_token_length."""

    name = "token_length"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)

        encoding = tiktoken.get_encoding(self.config.token_encoding)
        max_tokens = self.config.max_token_length

        over_limit_indices: list[int] = []
        over_limit_details: list[dict[str, int]] = []

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            # Skip None and non-string values
            if value is None or not isinstance(value, str):
                continue

            token_count = len(encoding.encode(value))
            if token_count > max_tokens:
                over_limit_indices.append(i)
                over_limit_details.append(
                    {
                        "row_index": i,
                        "token_count": token_count,
                    }
                )

        if over_limit_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(over_limit_indices)} rows exceeding "
                        f"max token length ({max_tokens})"
                    ),
                    row_indices=over_limit_indices,
                    details={
                        "max_token_length": max_tokens,
                        "over_limit_rows": over_limit_details,
                    },
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "over_limit_count": len(over_limit_indices),
        }
        return result
