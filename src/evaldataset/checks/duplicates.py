"""Duplicate checks: exact duplicate detection via SHA-256 hashing."""

from __future__ import annotations

from collections import defaultdict

from datasets import Dataset

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity
from evaldataset.utils.hashing import sha256_hash


@register
class ExactDuplicateChecker(BaseChecker):
    """Detect exact duplicate rows by comparing SHA-256 hashes of the text field."""

    name = "exact_duplicate"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)

        # Skip if config says so
        if self.config.skip_duplicates:
            result.stats = {"skipped": True}
            return result

        # Build hash -> list of row indices
        hash_to_indices: dict[str, list[int]] = defaultdict(list)

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or not isinstance(value, str):
                continue
            h = sha256_hash(value)
            hash_to_indices[h].append(i)

        # Collect all row indices where hash appears 2+ times
        duplicate_indices: list[int] = []
        for indices in hash_to_indices.values():
            if len(indices) >= 2:
                duplicate_indices.extend(indices)

        # Sort for deterministic output
        duplicate_indices.sort()

        if duplicate_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(duplicate_indices)} rows that are exact "
                        f"duplicates (by SHA-256 hash)"
                    ),
                    row_indices=duplicate_indices,
                )
            )

        total_rows = len(dataset)
        unique_count = len(hash_to_indices)

        result.stats = {
            "total_rows": total_rows,
            "duplicate_count": len(duplicate_indices),
            "unique_count": unique_count,
        }
        return result
