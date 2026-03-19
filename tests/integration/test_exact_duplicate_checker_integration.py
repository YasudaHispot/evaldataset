"""Integration tests for ExactDuplicateChecker.

IT: ExactDuplicateChecker
Source: docs/design.md — ExactDuplicateChecker 受入条件 (AC-07-01, AC-07-02, AC-07-03)
"""

from datasets import Dataset

from evaldataset.checks.duplicates import ExactDuplicateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestExactDuplicateCheckerIntegration:
    """
    IT: ExactDuplicateChecker
    Source: docs/design.md — ExactDuplicateChecker 受入条件 (AC-07-01, AC-07-02, AC-07-03)
    """

    def test_exact_duplicates_detected(self):
        """
        AC-07-01: 完全一致重複の検出

        Given: 同一テキスト "Hello world" が3件、ユニーク2件（計5件）のDataset
        When: ExactDuplicateChecker.check(dataset, text_field="text") を実行
        Then: severity=WARNING の Issue が1件、row_indices に重複3件、stats["duplicate_count"] が3
        """
        # Arrange (Given)
        texts = [
            "Hello world",
            "Unique text one",
            "Hello world",
            "Unique text two",
            "Hello world",
        ]
        dataset = Dataset.from_dict({"text": texts})
        config = CheckerConfig()
        checker = ExactDuplicateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert len(warning_issues[0].row_indices) == 3
        assert result.stats["duplicate_count"] == 3

    def test_no_duplicates_no_issues(self):
        """
        AC-07-02: 重複なしデータでの無検出

        Given: 全レコードのテキストがそれぞれ異なる Dataset
        When: ExactDuplicateChecker.check(dataset, text_field="text") を実行
        Then: CheckResult.issues が空、stats["duplicate_count"] が0
        """
        # Arrange (Given)
        texts = ["Text A", "Text B", "Text C"]
        dataset = Dataset.from_dict({"text": texts})
        config = CheckerConfig()
        checker = ExactDuplicateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
        assert result.stats["duplicate_count"] == 0

    def test_skip_duplicates_flag(self):
        """
        AC-07-03: skip_duplicates=True 時のスキップ

        Given: skip_duplicates=True の設定で、重複レコードを含む Dataset
        When: ExactDuplicateChecker.check(dataset, text_field="text") を実行
        Then: Issue なし、stats に "skipped": True
        """
        # Arrange (Given)
        texts = ["Hello world", "Hello world", "Unique"]
        dataset = Dataset.from_dict({"text": texts})
        config = CheckerConfig(skip_duplicates=True)
        checker = ExactDuplicateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
        assert result.stats.get("skipped") is True
