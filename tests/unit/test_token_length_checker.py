"""Unit tests for TokenLengthChecker.

Covers:
- AC-10-01: Token count exceeding max_token_length -- severity=WARNING, details contain actual token count
- AC-10-02: Boundary value (exactly max_token_length) -- no Issue
- None/non-string value skipping
- Empty dataset
- stats["total_rows"] and stats["over_limit_count"] verification
- checker_name == "token_length" verification
- Multiple rows exceeding limit
- Custom config (token_encoding, max_token_length)
"""

from __future__ import annotations

import tiktoken
import pytest
from datasets import Dataset

from evaldataset.checks.content import TokenLengthChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestTokenLengthChecker:
    """TokenLengthChecker unit tests."""

    # --- Fixtures ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """Default CheckerConfig with cl100k_base and max_token_length=8192."""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> TokenLengthChecker:
        """TokenLengthChecker instance with default config."""
        return TokenLengthChecker(config)

    # --- Helpers ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """Create a test Dataset. Supports None values."""
        return Dataset.from_dict({"text": texts})

    @staticmethod
    def _make_text_with_tokens(n: int) -> str:
        """Create text that is exactly n tokens with cl100k_base.

        Each ' a' is encoded as a single token (token id 264) in cl100k_base.
        """
        return " a" * n

    # --- AC-10-01: Token count exceeding max_token_length ---

    def test_over_limit_detected(self, checker: TokenLengthChecker) -> None:
        """AC-10-01: Text with 8193 tokens produces severity=WARNING Issue."""
        text = self._make_text_with_tokens(8193)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1, "8193 tokens should produce exactly 1 WARNING"

    def test_over_limit_row_indices(self, checker: TokenLengthChecker) -> None:
        """AC-10-01: row_indices contains the index of the over-limit row."""
        texts = [
            self._make_text_with_tokens(100),   # index 0: under limit
            self._make_text_with_tokens(8193),   # index 1: over limit
            self._make_text_with_tokens(50),     # index 2: under limit
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        affected = [idx for issue in result.issues for idx in issue.row_indices]
        assert 1 in affected, "index 1 (over limit) should be in row_indices"
        assert 0 not in affected, "index 0 (under limit) should not be in row_indices"
        assert 2 not in affected, "index 2 (under limit) should not be in row_indices"

    def test_over_limit_details_contain_token_count(
        self, checker: TokenLengthChecker
    ) -> None:
        """AC-10-01: details contains the actual token count for over-limit rows."""
        text = self._make_text_with_tokens(8193)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        issue = result.issues[0]
        assert "over_limit_rows" in issue.details, (
            "details should contain 'over_limit_rows'"
        )
        over_limit_rows = issue.details["over_limit_rows"]
        assert len(over_limit_rows) == 1
        assert over_limit_rows[0]["token_count"] == 8193, (
            "token_count should be 8193"
        )

    def test_over_limit_details_contain_row_index(
        self, checker: TokenLengthChecker
    ) -> None:
        """AC-10-01: details over_limit_rows entries include row_index."""
        text = self._make_text_with_tokens(8193)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        over_limit_rows = result.issues[0].details["over_limit_rows"]
        assert over_limit_rows[0]["row_index"] == 0

    def test_over_limit_severity_is_warning(
        self, checker: TokenLengthChecker
    ) -> None:
        """AC-10-01: Issue severity is WARNING."""
        text = self._make_text_with_tokens(8193)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.severity == Severity.WARNING

    # --- AC-10-02: Boundary value (exactly max_token_length) ---

    def test_exactly_max_tokens_no_issue(self, checker: TokenLengthChecker) -> None:
        """AC-10-02: Text with exactly 8192 tokens produces no Issue."""
        text = self._make_text_with_tokens(8192)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            "Exactly 8192 tokens should not produce any Issue"
        )

    def test_one_below_max_tokens_no_issue(
        self, checker: TokenLengthChecker
    ) -> None:
        """8191 tokens (one below limit) produces no Issue."""
        text = self._make_text_with_tokens(8191)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "8191 tokens should not produce any Issue"

    def test_one_above_max_tokens_detected(
        self, checker: TokenLengthChecker
    ) -> None:
        """8193 tokens (one above limit) produces Issue."""
        text = self._make_text_with_tokens(8193)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "8193 tokens should produce an Issue"

    # --- None/non-string skipping ---

    def test_none_values_are_skipped(self, checker: TokenLengthChecker) -> None:
        """None values are skipped without error."""
        dataset = Dataset.from_dict({"text": [None, "short text", None]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "None + short text should produce no Issue"

    def test_none_only_no_issues(self, checker: TokenLengthChecker) -> None:
        """Dataset with only None values produces no Issue."""
        dataset = Dataset.from_dict({"text": [None, None, None]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["over_limit_count"] == 0

    def test_non_string_values_are_skipped(self) -> None:
        """Non-string values (int) are skipped without error."""
        config = CheckerConfig(max_token_length=10)
        checker = TokenLengthChecker(config)
        # Force non-string data by building dataset with ints
        dataset = Dataset.from_dict({"text": [123, 456]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    # --- Empty dataset ---

    def test_empty_dataset_no_issues(self, checker: TokenLengthChecker) -> None:
        """Empty Dataset produces no Issues."""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_empty_dataset_stats(self, checker: TokenLengthChecker) -> None:
        """Empty Dataset has correct stats."""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 0
        assert result.stats["over_limit_count"] == 0

    # --- Stats verification ---

    def test_stats_total_rows(self, checker: TokenLengthChecker) -> None:
        """stats['total_rows'] reflects actual dataset size."""
        texts = ["short", "text", "here"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 3

    def test_stats_over_limit_count_zero(
        self, checker: TokenLengthChecker
    ) -> None:
        """stats['over_limit_count'] is 0 when all rows are within limit."""
        texts = ["short text", "another short text"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["over_limit_count"] == 0

    def test_stats_over_limit_count_matches_detected(self) -> None:
        """stats['over_limit_count'] matches number of rows exceeding limit."""
        config = CheckerConfig(max_token_length=5)
        checker = TokenLengthChecker(config)
        texts = [
            self._make_text_with_tokens(3),   # under
            self._make_text_with_tokens(6),   # over
            self._make_text_with_tokens(10),  # over
            self._make_text_with_tokens(4),   # under
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["over_limit_count"] == 2
        assert result.stats["total_rows"] == 4

    # --- checker_name verification ---

    def test_checker_name_is_token_length(
        self, checker: TokenLengthChecker
    ) -> None:
        """checker_name is 'token_length'."""
        dataset = self._make_dataset(["some text"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "token_length"

    def test_issue_checker_field_matches_name(self) -> None:
        """Issue.checker field matches 'token_length'."""
        config = CheckerConfig(max_token_length=5)
        checker = TokenLengthChecker(config)
        text = self._make_text_with_tokens(10)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == "token_length"

    # --- Multiple rows exceeding limit ---

    def test_multiple_rows_over_limit(self) -> None:
        """Multiple rows exceeding limit are all detected."""
        config = CheckerConfig(max_token_length=100)
        checker = TokenLengthChecker(config)
        texts = [
            self._make_text_with_tokens(101),  # index 0: over
            self._make_text_with_tokens(50),   # index 1: under
            self._make_text_with_tokens(200),  # index 2: over
            self._make_text_with_tokens(99),   # index 3: under
            self._make_text_with_tokens(150),  # index 4: over
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        affected = sorted(
            {idx for issue in result.issues for idx in issue.row_indices}
        )
        assert affected == [0, 2, 4]
        assert result.stats["over_limit_count"] == 3

    def test_multiple_rows_details_contain_all_token_counts(self) -> None:
        """details contain token counts for all over-limit rows."""
        config = CheckerConfig(max_token_length=100)
        checker = TokenLengthChecker(config)
        texts = [
            self._make_text_with_tokens(101),
            self._make_text_with_tokens(200),
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        over_limit_rows = result.issues[0].details["over_limit_rows"]
        token_counts = {r["token_count"] for r in over_limit_rows}
        assert 101 in token_counts
        assert 200 in token_counts

    # --- Custom config ---

    def test_custom_max_token_length(self) -> None:
        """Custom max_token_length is respected."""
        config = CheckerConfig(max_token_length=10)
        checker = TokenLengthChecker(config)
        texts = [
            self._make_text_with_tokens(11),   # over
            self._make_text_with_tokens(10),   # exactly at limit
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        assert result.stats["over_limit_count"] == 1
        affected = [idx for issue in result.issues for idx in issue.row_indices]
        assert 0 in affected
        assert 1 not in affected

    def test_details_max_token_length_field(self) -> None:
        """details include max_token_length used for the check."""
        config = CheckerConfig(max_token_length=50)
        checker = TokenLengthChecker(config)
        text = self._make_text_with_tokens(51)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        assert result.issues[0].details["max_token_length"] == 50

    # --- All rows within limit ---

    def test_all_rows_within_limit_no_issues(
        self, checker: TokenLengthChecker
    ) -> None:
        """When all rows are within limit, no Issues are produced."""
        texts = [
            self._make_text_with_tokens(100),
            self._make_text_with_tokens(500),
            self._make_text_with_tokens(8000),
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["over_limit_count"] == 0
