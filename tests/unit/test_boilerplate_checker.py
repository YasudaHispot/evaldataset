"""Unit tests for BoilerplateChecker.

Covers:
- AC-11-01: Boilerplate pattern detection -- severity=INFO, matched pattern in details
- AC-11-02: URL/Email density exceeding threshold -- severity=WARNING
- AC-11-03: Normal text produces no issues
- None/non-string value skipping
- Empty dataset
- Stats verification (total_rows, boilerplate_count, high_url_density_count, high_email_density_count)
- checker_name == "boilerplate"
- Email density exceeding threshold
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.content import BoilerplateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestBoilerplateChecker:
    """BoilerplateChecker unit tests."""

    # --- Fixtures ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """Default CheckerConfig."""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> BoilerplateChecker:
        """BoilerplateChecker with default config."""
        return BoilerplateChecker(config)

    # --- Helpers ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """Create a test Dataset. Supports None values."""
        return Dataset.from_dict({"text": texts})

    # --- AC-11-01: Boilerplate pattern detection ---

    def test_copyright_text_detected(self, checker: BoilerplateChecker) -> None:
        """AC-11-01: Text starting with 'Copyright 2023 Example Corp' produces severity=INFO Issue."""
        texts = ["Copyright 2023 Example Corp. All rights reserved. This is some text."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1, "Copyright text should produce exactly 1 INFO Issue"

    def test_copyright_text_details_contain_matched_pattern(
        self, checker: BoilerplateChecker
    ) -> None:
        """AC-11-01: Issue details contain the matched pattern."""
        texts = ["Copyright 2023 Example Corp. Some additional content here."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        details = info_issues[0].details
        assert "boilerplate_matches" in details, "details should contain 'boilerplate_matches'"
        matches = details["boilerplate_matches"]
        assert len(matches) == 1
        assert "matched_pattern" in matches[0], "Each match should contain 'matched_pattern'"

    def test_cookie_policy_detected(self, checker: BoilerplateChecker) -> None:
        """Boilerplate pattern 'cookie policy' is detected."""
        texts = ["Please accept our cookie policy to continue browsing."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1

    def test_privacy_policy_detected(self, checker: BoilerplateChecker) -> None:
        """Boilerplate pattern 'privacy policy' is detected."""
        texts = ["Read our privacy policy for more details about data handling."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1

    def test_terms_of_service_detected(self, checker: BoilerplateChecker) -> None:
        """Boilerplate pattern 'terms of service' is detected."""
        texts = ["By using this site, you agree to our terms of service."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1

    def test_subscribe_newsletter_detected(self, checker: BoilerplateChecker) -> None:
        """Boilerplate pattern 'subscribe to our newsletter' is detected."""
        texts = ["Subscribe to our newsletter for weekly updates."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1

    def test_boilerplate_row_indices(self, checker: BoilerplateChecker) -> None:
        """AC-11-01: row_indices contains only boilerplate rows."""
        texts = [
            "Clean text about machine learning.",
            "Copyright 2023 Example Corp.",
            "Another clean text about NLP.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        assert 1 in info_issues[0].row_indices
        assert 0 not in info_issues[0].row_indices
        assert 2 not in info_issues[0].row_indices

    def test_multiple_boilerplate_rows(self, checker: BoilerplateChecker) -> None:
        """Multiple rows with boilerplate patterns are all detected."""
        texts = [
            "Copyright 2023 Example Corp.",
            "Clean text.",
            "Please read our privacy policy.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        assert 0 in info_issues[0].row_indices
        assert 2 in info_issues[0].row_indices
        assert 1 not in info_issues[0].row_indices

    def test_one_match_per_row(self, checker: BoilerplateChecker) -> None:
        """A row matching multiple boilerplate patterns produces only one match entry."""
        texts = ["Copyright 2023 Corp. All rights reserved. Privacy policy applies."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        matches = info_issues[0].details["boilerplate_matches"]
        assert len(matches) == 1, "Only one match per row should be recorded"

    # --- AC-11-02: URL/Email density exceeding threshold ---

    def test_high_url_density_detected(self) -> None:
        """AC-11-02: Text with 15% URL density (threshold 0.1) produces severity=WARNING."""
        config = CheckerConfig(max_url_density=0.1)
        checker = BoilerplateChecker(config)

        # Create text where ~15% of characters are URL
        # "http://example.com" is 18 chars; we need total text of ~120 chars
        # 18/120 = 0.15, which is > 0.1
        padding = "a" * 102
        text = f"http://example.com {padding}"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) >= 1, "High URL density should produce WARNING"
        # Find the URL density warning specifically
        url_warnings = [
            i for i in warning_issues if "URL" in i.message or "url" in i.message.lower()
        ]
        assert len(url_warnings) == 1

    def test_high_email_density_detected(self) -> None:
        """Email density exceeding max_email_density produces severity=WARNING."""
        config = CheckerConfig(max_email_density=0.05)
        checker = BoilerplateChecker(config)

        # "user@example.com" is 16 chars; we need total where 16/total > 0.05
        # 16/100 = 0.16 > 0.05
        padding = "a" * 84
        text = f"user@example.com {padding}"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) >= 1, "High email density should produce WARNING"
        email_warnings = [
            i for i in warning_issues if "email" in i.message.lower()
        ]
        assert len(email_warnings) == 1

    def test_url_density_at_threshold_no_warning(self) -> None:
        """URL density exactly at threshold does not produce a WARNING (strict >)."""
        config = CheckerConfig(max_url_density=0.5)
        checker = BoilerplateChecker(config)

        # Just below or at threshold -- no warning expected
        # Use text with very low URL content
        text = "This is a simple text with no URLs at all."
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        url_warnings = [
            i for i in result.issues
            if i.severity == Severity.WARNING and "url" in i.message.lower()
        ]
        assert len(url_warnings) == 0

    # --- AC-11-03: Normal text produces no issues ---

    def test_clean_text_no_issues(self, checker: BoilerplateChecker) -> None:
        """AC-11-03: Text without boilerplate or high density URLs/emails has no issues."""
        texts = [
            "This is a normal article about machine learning techniques.",
            "Natural language processing has made great advances in recent years.",
            "Deep learning models require large amounts of training data.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "Clean text should produce no issues"

    # --- None/non-string value skipping ---

    def test_none_values_skipped(self, checker: BoilerplateChecker) -> None:
        """None values are skipped without error."""
        dataset = Dataset.from_dict({"text": [None, "Copyright 2023 Corp.", None]})
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        assert 1 in info_issues[0].row_indices
        assert 0 not in info_issues[0].row_indices
        assert 2 not in info_issues[0].row_indices

    def test_none_only_dataset(self, checker: BoilerplateChecker) -> None:
        """Dataset with only None values produces no issues."""
        dataset = Dataset.from_dict({"text": [None, None, None]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_non_string_values_skipped(self, checker: BoilerplateChecker) -> None:
        """Non-string values (e.g., int) are skipped without error."""
        dataset = Dataset.from_dict({"text": [123, 456]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    # --- Empty dataset ---

    def test_empty_dataset_no_issues(self, checker: BoilerplateChecker) -> None:
        """Empty dataset produces no issues."""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_empty_dataset_stats(self, checker: BoilerplateChecker) -> None:
        """Empty dataset stats show zero counts."""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 0
        assert result.stats["boilerplate_count"] == 0
        assert result.stats["high_url_density_count"] == 0
        assert result.stats["high_email_density_count"] == 0

    # --- Stats verification ---

    def test_stats_total_rows(self, checker: BoilerplateChecker) -> None:
        """stats['total_rows'] reflects the dataset size."""
        texts = ["text1", "text2", "text3"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 3

    def test_stats_boilerplate_count(self, checker: BoilerplateChecker) -> None:
        """stats['boilerplate_count'] reflects detected boilerplate rows."""
        texts = [
            "Copyright 2023 Corp.",
            "Clean text.",
            "All rights reserved by Corp.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["boilerplate_count"] == 2

    def test_stats_high_url_density_count(self) -> None:
        """stats['high_url_density_count'] reflects detected high URL density rows."""
        config = CheckerConfig(max_url_density=0.1)
        checker = BoilerplateChecker(config)

        padding = "a" * 102
        texts = [
            f"http://example.com {padding}",  # ~15% URL density
            "Clean text without URLs.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["high_url_density_count"] == 1

    def test_stats_high_email_density_count(self) -> None:
        """stats['high_email_density_count'] reflects detected high email density rows."""
        config = CheckerConfig(max_email_density=0.05)
        checker = BoilerplateChecker(config)

        padding = "a" * 84
        texts = [
            f"user@example.com {padding}",  # ~16% email density
            "Clean text without emails.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["high_email_density_count"] == 1

    # --- checker_name verification ---

    def test_checker_name_is_boilerplate(self, checker: BoilerplateChecker) -> None:
        """checker_name is 'boilerplate'."""
        dataset = self._make_dataset(["plain text"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "boilerplate"

    def test_issue_checker_field_matches_name(self, checker: BoilerplateChecker) -> None:
        """Issue.checker field matches CheckResult.checker_name."""
        texts = ["Copyright 2023 Corp."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == "boilerplate"

    # --- Severity distinction: boilerplate=INFO, density violation=WARNING ---

    def test_boilerplate_only_produces_info_not_warning(
        self, checker: BoilerplateChecker
    ) -> None:
        """Boilerplate match (without density violation) produces INFO, not WARNING."""
        texts = ["Copyright 2023 Example Corp. Some plain text here."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert info_issues, "Boilerplate match should produce INFO"
        assert not warning_issues, (
            "Boilerplate match without density violation should not produce WARNING"
        )

    def test_url_density_violation_produces_warning_not_info(self) -> None:
        """URL density violation produces WARNING, not INFO."""
        config = CheckerConfig(max_url_density=0.1, boilerplate_patterns=[])
        checker = BoilerplateChecker(config)

        padding = "a" * 102
        text = f"http://example.com {padding}"
        dataset = Dataset.from_dict({"text": [text]})
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert warning_issues, "URL density violation should produce WARNING"
        assert not info_issues, (
            "URL density violation with no boilerplate patterns should not produce INFO"
        )

    def test_email_density_violation_produces_warning_not_info(self) -> None:
        """Email density violation produces WARNING, not INFO."""
        config = CheckerConfig(max_email_density=0.05, boilerplate_patterns=[])
        checker = BoilerplateChecker(config)

        padding = "a" * 84
        text = f"user@example.com {padding}"
        dataset = Dataset.from_dict({"text": [text]})
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert warning_issues, "Email density violation should produce WARNING"
        assert not info_issues, (
            "Email density violation with no boilerplate patterns should not produce INFO"
        )

    # --- AC-11-01: details key verification ---

    def test_copyright_details_boilerplate_matches_row_index(
        self, checker: BoilerplateChecker
    ) -> None:
        """AC-11-01: boilerplate_matches entry contains row_index."""
        texts = [
            "Clean text.",
            "Copyright 2023 Example Corp.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert info_issues
        matches = info_issues[0].details["boilerplate_matches"]
        row_indices_in_matches = [m["row_index"] for m in matches]
        assert 1 in row_indices_in_matches, (
            "boilerplate_matches should include row_index 1"
        )

    def test_all_rights_reserved_case_insensitive(
        self, checker: BoilerplateChecker
    ) -> None:
        """Default pattern for 'all rights reserved' is case-insensitive."""
        texts = ["ALL RIGHTS RESERVED BY EXAMPLE CORP 2024."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert info_issues, "ALL RIGHTS RESERVED (uppercase) should also be detected"

    # --- Registration verification ---

    def test_registered_in_registry(self) -> None:
        """BoilerplateChecker is registered with name 'boilerplate'."""
        from evaldataset.checks.registry import get_checker

        cls = get_checker("boilerplate")
        assert cls is BoilerplateChecker
