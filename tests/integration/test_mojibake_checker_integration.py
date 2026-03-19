"""Integration tests for MojibakeChecker.

IT: MojibakeChecker
Source: docs/design.md — MojibakeChecker 受入条件 (AC-06-01, AC-06-02)
"""

from datasets import Dataset

from evaldataset.checks.text_quality import MojibakeChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestMojibakeCheckerIntegration:
    """
    IT: MojibakeChecker
    Source: docs/design.md — MojibakeChecker 受入条件 (AC-06-01, AC-06-02)
    """

    def test_mojibake_text_detected_as_warning(self):
        """
        AC-06-01: 文字化けテキストの検出

        Given: ftfy.fix_text で修正が発生するテキスト（例: "â€œhelloâ€\x9d"）を含むレコードの Dataset
        When: MojibakeChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件以上あり、該当レコードのインデックスが含まれる
        """
        # Arrange (Given)
        mojibake_text = "\u00e2\u0080\u009chello\u00e2\u0080\u009d"  # â€œhelloâ€\x9d
        normal_text = "This is perfectly normal English text without any encoding issues."
        dataset = Dataset.from_dict({"text": [mojibake_text, normal_text]})
        config = CheckerConfig()
        checker = MojibakeChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert 0 in warning_issues[0].row_indices

    def test_normal_text_no_issues(self):
        """
        AC-06-02: 正常テキストでの無検出

        Given: ftfy.fix_text で変化しない正常な UTF-8 テキストの Dataset
        When: MojibakeChecker.check(dataset, text_field="text") を実行する
        Then: CheckResult.issues が空リストである
        """
        # Arrange (Given)
        texts = [
            "This is perfectly normal English text.",
            "Another clean document without encoding problems.",
            "Unicode is fine: cafe, resume, naive.",
        ]
        dataset = Dataset.from_dict({"text": texts})
        config = CheckerConfig()
        checker = MojibakeChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
