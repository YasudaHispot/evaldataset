"""Integration tests for PiiChecker.

IT: PiiChecker
Source: docs/design.md — PiiChecker 受入条件 (AC-09-01, AC-09-02, AC-09-03)
"""

from datasets import Dataset

from evaldataset.checks.content import PiiChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestPiiCheckerIntegration:
    """
    IT: PiiChecker
    Source: docs/design.md — PiiChecker 受入条件 (AC-09-01, AC-09-02, AC-09-03)
    """

    def test_email_pii_detected(self):
        """
        AC-09-01: PII（メールアドレス）の検出

        Given: detect_pii=True の設定で、user@example.com を含むテキスト1件
        When: PiiChecker.check(dataset, text_field="text") を実行
        Then: severity=WARNING の Issue が1件、details に pii_type: "email" 情報
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({
            "text": ["Contact us at user@example.com for more info."]
        })
        config = CheckerConfig(detect_pii=True)
        checker = PiiChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert "email" in str(warning_issues[0].details)

    def test_detect_pii_false_skips(self):
        """
        AC-09-02: detect_pii=False 時のスキップ

        Given: detect_pii=False の設定で、PIIを含む Dataset
        When: PiiChecker.check(dataset, text_field="text") を実行
        Then: Issue が生成されない
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({
            "text": ["Contact user@example.com now."]
        })
        config = CheckerConfig(detect_pii=False)
        checker = PiiChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []

    def test_no_pii_no_issues(self):
        """
        AC-09-03: PIIなしデータでの無検出

        Given: detect_pii=True の設定で、PIIパターンを含まないテキスト
        When: PiiChecker.check(dataset, text_field="text") を実行
        Then: CheckResult.issues が空リスト
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({
            "text": [
                "This is clean text without any personal information.",
                "Another safe document with no sensitive data.",
            ]
        })
        config = CheckerConfig(detect_pii=True)
        checker = PiiChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
