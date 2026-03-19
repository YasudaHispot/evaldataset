"""Duplicate checks: exact and near-duplicate detection."""

from __future__ import annotations

from collections import defaultdict

from datasketch import MinHash, MinHashLSH
from datasets import Dataset

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.models import CheckResult, Issue, Severity
from evaldataset.utils.hashing import sha256_hash, text_to_shingles


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


@register
class NearDuplicateChecker(BaseChecker):
    """Detect near-duplicate rows using MinHash LSH for approximate Jaccard similarity."""

    name = "near_duplicate"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)

        # Skip if config says so
        if self.config.skip_duplicates:
            result.stats = {"skipped": True}
            return result

        num_perm = self.config.minhash_num_perm
        threshold = self.config.minhash_threshold

        # Build MinHash for each valid row
        minhashes: dict[int, MinHash] = {}

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            # Skip None and non-string values
            if value is None or not isinstance(value, str):
                continue
            shingles = text_to_shingles(value)
            # Skip rows with empty shingles (extremely short text)
            if not shingles:
                continue
            mh = MinHash(num_perm=num_perm)
            for s in shingles:
                mh.update(s.encode("utf-8"))
            minhashes[i] = mh

        # Build LSH index and query for near-duplicates
        near_duplicate_indices: set[int] = set()

        if minhashes:
            lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
            for idx, mh in minhashes.items():
                lsh.insert(str(idx), mh)

            for idx, mh in minhashes.items():
                candidates = lsh.query(mh)
                # candidates includes self, so look for others
                for candidate in candidates:
                    candidate_idx = int(candidate)
                    if candidate_idx != idx:
                        near_duplicate_indices.add(idx)
                        near_duplicate_indices.add(candidate_idx)

        sorted_indices = sorted(near_duplicate_indices)

        if sorted_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    message=(
                        f"Found {len(sorted_indices)} rows that are near-duplicates "
                        f"(MinHash Jaccard threshold={threshold})"
                    ),
                    row_indices=sorted_indices,
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "near_duplicate_count": len(sorted_indices),
        }
        return result
