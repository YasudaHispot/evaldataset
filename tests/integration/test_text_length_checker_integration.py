"""Integration tests for TextLengthChecker.

IT: TextLengthChecker
Source: docs/design.md — TextLengthChecker 受入条件 (AC-03-01, AC-03-02, AC-03-03)
"""

from datasets import Dataset

from evaldataset.checks.text_quality import TextLengthChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestTextLengthCheckerIntegration:
    """
    IT: TextLengthChecker
    Source: docs/design.md — TextLengthChecker 受入条件
    """

    def test_short_text_detected_as_warning(self):
        """
        AC-03-01: 短すぎるテキストの検出

        Given: min_length=50 の設定で、49文字のテキスト1件と50文字以上4件のDataset
        When: TextLengthChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件あり、row_indices に49文字レコードのインデックスが含まれる
        """
        # Arrange (Given)
        short_text = "a" * 49  # 49 chars
        normal_texts = ["b" * 60 for _ in range(4)]  # 60 chars each
        dataset = Dataset.from_dict({"text": [short_text] + normal_texts})
        config = CheckerConfig(min_length=50)
        checker = TextLengthChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        all_row_indices = []
        for issue in warning_issues:
            all_row_indices.extend(issue.row_indices)
        assert 0 in all_row_indices  # index 0 is the 49-char record

    def test_boundary_min_length_no_warning(self):
        """
        AC-03-02: 境界値（ちょうど min_length）での無検出

        Given: min_length=50 の設定で、ちょうど50文字のテキストを含む Dataset
        When: TextLengthChecker.check(dataset, text_field="text") を実行する
        Then: WARNING の Issue が発生しない（50文字は許容範囲）
        """
        # Arrange (Given)
        boundary_text = "c" * 50  # exactly 50 chars
        dataset = Dataset.from_dict({"text": [boundary_text]})
        config = CheckerConfig(min_length=50)
        checker = TextLengthChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 0

    def test_long_text_detected_as_warning(self):
        """
        AC-03-03: 長すぎるテキストの検出

        Given: max_length=100000 の設定で、100,001文字のテキスト1件のDataset
        When: TextLengthChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件あり、該当レコードの row_indices が含まれる
        """
        # Arrange (Given)
        long_text = "d" * 100_001  # 100,001 chars
        dataset = Dataset.from_dict({"text": [long_text]})
        config = CheckerConfig(max_length=100_000)
        checker = TextLengthChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        all_row_indices = []
        for issue in warning_issues:
            all_row_indices.extend(issue.row_indices)
        assert 0 in all_row_indices  # index 0 is the 100,001-char record
