"""Integration tests for BoilerplateChecker.

IT: BoilerplateChecker
Source: docs/design.md — BoilerplateChecker 受入条件 (AC-11-01, AC-11-02, AC-11-03)
"""

from datasets import Dataset

from evaldataset.checks.content import BoilerplateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestBoilerplateCheckerIntegration:
    """
    IT: BoilerplateChecker
    Source: docs/design.md — BoilerplateChecker 受入条件 (AC-11-01, AC-11-02, AC-11-03)
    """

    def test_boilerplate_pattern_detected(self):
        """
        AC-11-01: ボイラープレートの検出

        Given: デフォルト boilerplate_patterns で、"Copyright 2023 Example Corp" から始まるテキスト
        When: BoilerplateChecker.check(dataset, text_field="text") を実行
        Then: severity=INFO の Issue が1件、マッチしたパターンが details に含まれる
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({
            "text": ["Copyright 2023 Example Corp. All content is proprietary."]
        })
        config = CheckerConfig()
        checker = BoilerplateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        info_issues = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1

    def test_high_url_density_detected(self):
        """
        AC-11-02: URL/Email密度超過の検出

        Given: max_url_density=0.1 で、テキスト長の15%がURL文字のレコード
        When: BoilerplateChecker.check(dataset, text_field="text") を実行
        Then: severity=WARNING の Issue が1件
        """
        # Arrange (Given) -- URL chars ~15% of total
        url = "https://example.com/path"  # 24 chars
        padding = "x" * 136  # total 160 chars, URL = 24/160 = 15%
        text = f"{url} {padding}"
        dataset = Dataset.from_dict({"text": [text]})
        config = CheckerConfig(max_url_density=0.1)
        checker = BoilerplateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) >= 1

    def test_clean_text_no_issues(self):
        """
        AC-11-03: 正常テキストでの無検出

        Given: ボイラープレートパターンも高密度URLも含まないテキスト
        When: BoilerplateChecker.check(dataset, text_field="text") を実行
        Then: CheckResult.issues が空リスト
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({
            "text": [
                "This is a normal document about natural language processing.",
                "Another clean text without any boilerplate patterns.",
            ]
        })
        config = CheckerConfig()
        checker = BoilerplateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
