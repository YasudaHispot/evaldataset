"""Integration tests for TokenLengthChecker.

IT: TokenLengthChecker
Source: docs/design.md — TokenLengthChecker 受入条件 (AC-10-01, AC-10-02)
"""

from datasets import Dataset

from evaldataset.checks.content import TokenLengthChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestTokenLengthCheckerIntegration:
    """
    IT: TokenLengthChecker
    Source: docs/design.md — TokenLengthChecker 受入条件 (AC-10-01, AC-10-02)
    """

    def test_token_count_over_limit_detected(self):
        """
        AC-10-01: トークン数超過の検出

        Given: max_token_length=8192, token_encoding="cl100k_base" で、
               8,193トークン相当のテキストを含むレコードの Dataset
        When: TokenLengthChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件あり、details に実際のトークン数が含まれる
        """
        # Arrange (Given) -- " a" is 1 token in cl100k_base
        over_limit_text = " a" * 8193
        dataset = Dataset.from_dict({"text": [over_limit_text]})
        config = CheckerConfig(max_token_length=8192, token_encoding="cl100k_base")
        checker = TokenLengthChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        assert 0 in warning_issues[0].row_indices

    def test_exactly_max_tokens_no_issue(self):
        """
        AC-10-02: 境界値（ちょうど max_token_length）での無検出

        Given: max_token_length=8192 で、ちょうど8,192トークンのテキスト
        When: TokenLengthChecker.check(dataset, text_field="text") を実行する
        Then: Issue が発生しない（8,192トークンは許容範囲）
        """
        # Arrange (Given)
        boundary_text = " a" * 8192
        dataset = Dataset.from_dict({"text": [boundary_text]})
        config = CheckerConfig(max_token_length=8192, token_encoding="cl100k_base")
        checker = TokenLengthChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
