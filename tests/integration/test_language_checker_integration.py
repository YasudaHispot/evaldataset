"""Integration tests for LanguageChecker.

IT: LanguageChecker
Source: docs/design.md — LanguageChecker 受入条件 (AC-04-01, AC-04-02)
"""

from datasets import Dataset

from evaldataset.checks.text_quality import LanguageChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestLanguageCheckerIntegration:
    """
    IT: LanguageChecker
    Source: docs/design.md — LanguageChecker 受入条件 (AC-04-01, AC-04-02)
    """

    def test_non_target_language_detected_as_warning(self):
        """
        AC-04-01: 許可外言語の検出

        Given: languages=["en"], language_threshold=0.5 の設定で、
               日本語テキスト1件と英語テキスト4件を含む Dataset
        When: LanguageChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件あり、日本語レコードの行インデックスが含まれる
        """
        # Arrange (Given)
        japanese_text = "これは日本語のテキストです。自然言語処理のテストに使用されるサンプルテキストで、十分な長さが必要です。言語検出の精度を確保するために長めに記述しています。"
        english_texts = [
            "This is a sufficiently long English text used for language detection testing purposes in the integration test suite.",
            "Natural language processing requires adequate text length to accurately identify the language of a given document.",
            "The language checker validates that all texts in the dataset conform to the expected language configuration settings.",
            "Integration testing ensures that the full pipeline works correctly from input dataset to quality check results.",
        ]
        dataset = Dataset.from_dict({"text": [japanese_text] + english_texts})
        config = CheckerConfig(languages=["en"], language_threshold=0.5)
        checker = LanguageChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert 0 in warning_issues[0].row_indices  # index 0 is Japanese

    def test_all_english_no_issues(self):
        """
        AC-04-02: 許可言語での無検出

        Given: languages=["en"] の設定で、全レコードが英語テキストの Dataset
        When: LanguageChecker.check(dataset, text_field="text") を実行する
        Then: CheckResult.issues が空リストである
        """
        # Arrange (Given)
        english_texts = [
            "This is a sufficiently long English text used for language detection testing purposes in the integration test suite.",
            "Natural language processing requires adequate text length to accurately identify the language of a given document.",
            "The language checker validates that all texts in the dataset conform to the expected language configuration settings.",
        ]
        dataset = Dataset.from_dict({"text": english_texts})
        config = CheckerConfig(languages=["en"], language_threshold=0.5)
        checker = LanguageChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
