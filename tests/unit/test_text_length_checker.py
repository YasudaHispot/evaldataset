"""Unit tests for TextLengthChecker.

Covers:
- AC-03-01: 短すぎるテキストの検出
- AC-03-02: 境界値（ちょうど min_length）での無検出
- AC-03-03: 長すぎるテキストの検出
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.text_quality import TextLengthChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestTextLengthChecker:
    """TextLengthChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """min_length=50, max_length=100000 の設定（デフォルト値と同じ）。"""
        return CheckerConfig(min_length=50, max_length=100_000)

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> TextLengthChecker:
        """TextLengthChecker インスタンス。"""
        return TextLengthChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-03-01: 短すぎるテキストの検出 ---

    def test_short_text_detection(self, checker: TextLengthChecker) -> None:
        """AC-03-01: 49文字のテキスト1件を含む Dataset で WARNING が1件発生する。"""
        short_text = "a" * 49  # 49文字（min_length=50 未満）
        normal_texts = ["b" * 100, "c" * 200, "d" * 50, "e" * 1000]

        dataset = self._make_dataset([short_text] + normal_texts)
        result = checker.check(dataset, text_field="text")

        # WARNING が1件あること
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1

        # 49文字レコード（インデックス0）が含まれること
        assert 0 in warnings[0].row_indices

    def test_short_text_row_index(self, checker: TextLengthChecker) -> None:
        """AC-03-01: WARNING の row_indices に短すぎるレコードのインデックスが含まれる。"""
        texts = [
            "b" * 100,  # index 0: 正常
            "a" * 49,   # index 1: 短すぎる
            "c" * 200,  # index 2: 正常
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
        short_issue = next(
            (i for i in warnings if any(idx == 1 for idx in i.row_indices)),
            None,
        )
        assert short_issue is not None, "インデックス1の短いテキストが row_indices に含まれるべき"

    def test_short_text_stats_too_short_count(self, checker: TextLengthChecker) -> None:
        """AC-03-01: stats['too_short_count'] が短すぎるレコード数と一致する。"""
        texts = [
            "a" * 49,   # 短すぎる
            "b" * 10,   # 短すぎる
            "c" * 100,  # 正常
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_short_count"] == 2

    # --- AC-03-02: 境界値（ちょうど min_length）での無検出 ---

    def test_boundary_min_length(self, checker: TextLengthChecker) -> None:
        """AC-03-02: ちょうど50文字のテキストでは WARNING が発生しない。"""
        exact_min = "a" * 50  # ちょうど min_length
        dataset = self._make_dataset([exact_min])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 0, "50文字は許容範囲なので WARNING は発生しないべき"

    def test_boundary_min_length_stats(self, checker: TextLengthChecker) -> None:
        """AC-03-02: 境界値50文字では too_short_count が0である。"""
        dataset = self._make_dataset(["a" * 50])
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_short_count"] == 0

    # --- AC-03-03: 長すぎるテキストの検出 ---

    def test_long_text_detection(self, checker: TextLengthChecker) -> None:
        """AC-03-03: 100,001文字のテキスト1件を含む Dataset で WARNING が1件発生する。"""
        long_text = "a" * 100_001  # max_length=100000 超
        dataset = self._make_dataset([long_text])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_long_text_row_index(self, checker: TextLengthChecker) -> None:
        """AC-03-03: WARNING の row_indices に長すぎるレコードのインデックスが含まれる。"""
        texts = [
            "b" * 100,       # index 0: 正常
            "a" * 100_001,   # index 1: 長すぎる
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
        long_issue = next(
            (i for i in warnings if any(idx == 1 for idx in i.row_indices)),
            None,
        )
        assert long_issue is not None, "インデックス1の長いテキストが row_indices に含まれるべき"

    def test_long_text_stats_too_long_count(self, checker: TextLengthChecker) -> None:
        """AC-03-03: stats['too_long_count'] が長すぎるレコード数と一致する。"""
        texts = [
            "a" * 100_001,   # 長すぎる
            "b" * 200_000,   # 長すぎる
            "c" * 100,       # 正常
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_long_count"] == 2

    # --- 境界値: ちょうど max_length での無検出 ---

    def test_boundary_max_length(self, checker: TextLengthChecker) -> None:
        """max_length ちょうど（100,000文字）では WARNING が発生しない。"""
        exact_max = "a" * 100_000  # ちょうど max_length
        dataset = self._make_dataset([exact_max])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 0, "100,000文字は許容範囲なので WARNING は発生しないべき"

    # --- 全て正常なテキスト ---

    def test_no_issues_when_all_texts_valid(self, checker: TextLengthChecker) -> None:
        """全テキストが min_length 以上 max_length 以下の場合、issues が空である。"""
        texts = ["a" * 50, "b" * 500, "c" * 1000, "d" * 100_000]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["too_short_count"] == 0
        assert result.stats["too_long_count"] == 0

    # --- 短すぎると長すぎるが混在するケース ---

    def test_mixed_short_and_long_texts(self, checker: TextLengthChecker) -> None:
        """短すぎると長すぎるテキストが混在する場合、両方が検出される。"""
        texts = [
            "a" * 49,        # index 0: 短すぎる
            "b" * 100,       # index 1: 正常
            "c" * 100_001,   # index 2: 長すぎる
            "d" * 500,       # index 3: 正常
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_short_count"] == 1
        assert result.stats["too_long_count"] == 1

        # いずれかの WARNING に index 0 が含まれること
        all_warning_indices = [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ]
        assert 0 in all_warning_indices, "短すぎるテキスト（index 0）が WARNING に含まれるべき"
        assert 2 in all_warning_indices, "長すぎるテキスト（index 2）が WARNING に含まれるべき"

    def test_mixed_short_and_long_severity_is_warning(
        self, checker: TextLengthChecker
    ) -> None:
        """短すぎる・長すぎるテキストの Issue の severity が WARNING であること。"""
        texts = [
            "a" * 10,        # 短すぎる
            "b" * 200_000,   # 長すぎる
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.severity == Severity.WARNING, (
                f"Issue の severity は WARNING であるべき: {issue.severity}"
            )

    # --- エッジケース ---

    def test_single_record_just_below_min(self, checker: TextLengthChecker) -> None:
        """1件のみのデータセットで49文字のテキストが WARNING になる。"""
        dataset = self._make_dataset(["a" * 49])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
        assert result.stats["too_short_count"] == 1

    def test_empty_dataset(self, checker: TextLengthChecker) -> None:
        """空の Dataset では issues が空で stats のカウントが 0 である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats.get("too_short_count", 0) == 0
        assert result.stats.get("too_long_count", 0) == 0

    def test_checker_name_in_result(self, checker: TextLengthChecker) -> None:
        """CheckResult.checker_name が設定されていること。"""
        dataset = self._make_dataset(["a" * 100])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name != ""

    def test_issue_checker_field_matches_checker_name(
        self, checker: TextLengthChecker
    ) -> None:
        """Issue.checker フィールドが CheckResult.checker_name と一致すること。"""
        dataset = self._make_dataset(["a" * 10])  # 短すぎる
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == result.checker_name

    def test_custom_min_length(self) -> None:
        """カスタム min_length=100 の設定で 99文字が WARNING になる。"""
        config = CheckerConfig(min_length=100, max_length=100_000)
        checker = TextLengthChecker(config)

        texts = [
            "a" * 99,   # 短すぎる（カスタム min_length=100 未満）
            "b" * 100,  # ちょうど min_length
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_short_count"] == 1

    def test_custom_max_length(self) -> None:
        """カスタム max_length=1000 の設定で 1001文字が WARNING になる。"""
        config = CheckerConfig(min_length=50, max_length=1000)
        checker = TextLengthChecker(config)

        texts = [
            "a" * 1000,  # ちょうど max_length（許容範囲内）
            "b" * 1001,  # 長すぎる
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["too_long_count"] == 1
