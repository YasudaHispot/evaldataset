"""Integration tests for HTMLChecker.

IT: HTMLChecker
Source: docs/design.md — HTMLChecker 受入条件 (AC-05-01, AC-05-02, AC-05-03)
"""

from datasets import Dataset

from evaldataset.checks.text_quality import HTMLChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestHTMLCheckerIntegration:
    """
    IT: HTMLChecker
    Source: docs/design.md — HTMLChecker 受入条件 (AC-05-01, AC-05-02)
    """

    def test_html_tags_detected_as_warning(self):
        """
        AC-05-01: HTMLタグ混入の検出

        Given: <p> <div> <span> 等のHTMLタグが5件以上含まれるテキストのレコードを含む Dataset
        When: HTMLChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が発生し、該当レコードのインデックスが含まれる
        """
        # Arrange (Given)
        html_text = "<html><body><p>Hello <b>world</b></p><div>content</div></body></html>"
        plain_text = "This is plain text without any HTML tags at all."
        dataset = Dataset.from_dict({"text": [html_text, plain_text]})
        config = CheckerConfig()
        checker = HTMLChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert 0 in warning_issues[0].row_indices

    def test_plain_text_no_issues(self):
        """
        AC-05-02: タグなしテキストでの無検出

        Given: HTMLタグを一切含まないプレーンテキストの Dataset
        When: HTMLChecker.check(dataset, text_field="text") を実行する
        Then: CheckResult.issues が空リストである
        """
        # Arrange (Given)
        texts = [
            "This is plain text without any HTML tags.",
            "Another plain text document for testing purposes.",
            "No markup here, just regular text content.",
        ]
        dataset = Dataset.from_dict({"text": texts})
        config = CheckerConfig()
        checker = HTMLChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []

    def test_comparison_operators_not_detected_as_html(self):
        """
        AC-05-03: ソースコードの比較演算子を誤検出しない

        Given: JavaScript/Python 等のソースコードで比較演算子（<, <=, >, >=）や
               JSDoc 型注釈（<*>, Array.<number>）を含むが、実際の HTML タグを
               含まないテキストの Dataset
        When: HTMLChecker.check(dataset, text_field="text") を実行する
        Then: CheckResult.issues が空リストである
               （比較演算子はHTMLタグとしてカウントされない）
        """
        # Arrange (Given)
        source_code_text = (
            "function compare(a, b) {\n"
            "  if (a < b) { return -1; }\n"
            "  if (a > b) { return 1; }\n"
            "  if (a <= b && b >= a) { return 0; }\n"
            "  var arr = new Array(a < b ? 10 : 20);\n"
            "  // @return {Array.<*>}\n"
            "}"
        )
        dataset = Dataset.from_dict({"text": [source_code_text]})
        config = CheckerConfig()
        checker = HTMLChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
