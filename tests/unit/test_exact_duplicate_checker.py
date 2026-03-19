"""Unit tests for ExactDuplicateChecker.

Covers:
- AC-07-01: 完全一致重複の検出（同一テキスト3件+ユニーク2件の計5件）
- AC-07-02: 重複なしデータでの無検出
- AC-07-03: skip_duplicates=True 時のスキップ
- 重複ペア（2件だけ同一）の検出
- None 値のスキップ
- 空データセット
- stats["duplicate_count"] の検証
- stats["unique_count"] の検証
- severity=WARNING の検証
- checker_name == "exact_duplicate" の検証
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.duplicates import ExactDuplicateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestExactDuplicateChecker:
    """ExactDuplicateChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """デフォルト設定（skip_duplicates=False）。"""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> ExactDuplicateChecker:
        """ExactDuplicateChecker インスタンス。"""
        return ExactDuplicateChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-07-01: 完全一致重複の検出 ---

    def test_exact_duplicates_detected(self, checker: ExactDuplicateChecker) -> None:
        """AC-07-01: 同一テキスト3件 + ユニーク2件 で WARNING が1件発生する。"""
        texts = [
            "Hello world",  # index 0: 重複
            "Unique text A",  # index 1: ユニーク
            "Hello world",  # index 2: 重複
            "Unique text B",  # index 3: ユニーク
            "Hello world",  # index 4: 重複
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_exact_duplicates_row_indices(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-01: row_indices に重複3件のインデックスが含まれる。"""
        texts = [
            "Hello world",  # index 0
            "Unique text A",  # index 1
            "Hello world",  # index 2
            "Unique text B",  # index 3
            "Hello world",  # index 4
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert sorted(warnings[0].row_indices) == [0, 2, 4]

    def test_exact_duplicates_stats_duplicate_count(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-01: stats['duplicate_count'] が3である。"""
        texts = [
            "Hello world",
            "Unique text A",
            "Hello world",
            "Unique text B",
            "Hello world",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["duplicate_count"] == 3

    def test_exact_duplicates_stats_total_rows(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-01: stats['total_rows'] がデータセットの行数と一致する。"""
        texts = [
            "Hello world",
            "Unique text A",
            "Hello world",
            "Unique text B",
            "Hello world",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 5

    def test_exact_duplicates_stats_unique_count(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-01: stats['unique_count'] がユニークハッシュの数と一致する。"""
        texts = [
            "Hello world",
            "Unique text A",
            "Hello world",
            "Unique text B",
            "Hello world",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        # "Hello world", "Unique text A", "Unique text B" = 3 unique hashes
        assert result.stats["unique_count"] == 3

    def test_exact_duplicates_severity_is_warning(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-01: 重複検出の Issue の severity が WARNING であること。"""
        texts = ["dup", "dup"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.severity == Severity.WARNING

    # --- AC-07-02: 重複なしデータでの無検出 ---

    def test_no_duplicates_no_issues(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-02: 全レコードが異なるテキストの場合、issues が空リストである。"""
        texts = ["text A", "text B", "text C", "text D"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_no_duplicates_stats_duplicate_count_zero(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """AC-07-02: 重複なし時、stats['duplicate_count'] が0である。"""
        texts = ["text A", "text B", "text C"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["duplicate_count"] == 0

    # --- AC-07-03: skip_duplicates=True 時のスキップ ---

    def test_skip_duplicates_no_issues(self) -> None:
        """AC-07-03: skip_duplicates=True で重複レコードがあっても Issue なし。"""
        config = CheckerConfig(skip_duplicates=True)
        checker = ExactDuplicateChecker(config)

        texts = ["dup text", "dup text", "unique"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_skip_duplicates_stats_skipped(self) -> None:
        """AC-07-03: skip_duplicates=True で stats に 'skipped': True が含まれる。"""
        config = CheckerConfig(skip_duplicates=True)
        checker = ExactDuplicateChecker(config)

        texts = ["dup text", "dup text", "unique"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("skipped") is True

    # --- エッジケース ---

    def test_empty_dataset(self, checker: ExactDuplicateChecker) -> None:
        """空の Dataset では issues が空で duplicate_count が0である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["duplicate_count"] == 0

    def test_none_values_skipped(self, checker: ExactDuplicateChecker) -> None:
        """None 値はスキップされ、重複として扱われない。"""
        dataset = Dataset.from_dict({"text": [None, None, "unique"]})
        result = checker.check(dataset, text_field="text")

        # None が2つあるが、None はスキップされるので重複なし
        assert result.issues == []
        assert result.stats["duplicate_count"] == 0

    def test_non_string_values_skipped(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """非文字列の値はスキップされ、重複として扱われない。"""
        # Dataset.from_dict with mixed types may cast, so use None as proxy
        dataset = Dataset.from_dict({"text": [None, "text A", "text B"]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["duplicate_count"] == 0

    def test_checker_name(self, checker: ExactDuplicateChecker) -> None:
        """CheckResult.checker_name が 'exact_duplicate' であること。"""
        dataset = self._make_dataset(["text A"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "exact_duplicate"

    def test_issue_checker_field_matches_name(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """Issue.checker フィールドが checker_name と一致すること。"""
        texts = ["dup", "dup"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == "exact_duplicate"

    def test_multiple_duplicate_groups(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """複数の重複グループがある場合、全ての重複行が検出される。"""
        texts = [
            "group A",  # index 0
            "group B",  # index 1
            "group A",  # index 2
            "group B",  # index 3
            "unique",   # index 4
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["duplicate_count"] == 4
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert sorted(warnings[0].row_indices) == [0, 1, 2, 3]

    def test_single_record_no_duplicates(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """1件のみのデータセットでは重複なし。"""
        dataset = self._make_dataset(["only one"])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["duplicate_count"] == 0
        assert result.stats["unique_count"] == 1

    def test_empty_dataset_unique_count_is_zero(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """空の Dataset では stats['unique_count'] も0である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("unique_count", 0) == 0

    def test_duplicate_pair_only_two_rows(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """重複ペア（2件だけ同一）の場合、その2件が row_indices に含まれる。"""
        texts = [
            "Unique alpha",  # index 0: ユニーク
            "Same text",     # index 1: 重複ペア
            "Unique beta",   # index 2: ユニーク
            "Same text",     # index 3: 重複ペア
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        flagged = warnings[0].row_indices
        assert 1 in flagged, "重複ペアの index 1 が row_indices に含まれるべき"
        assert 3 in flagged, "重複ペアの index 3 が row_indices に含まれるべき"
        assert 0 not in flagged, "ユニーク（index 0）は row_indices に含まれないべき"
        assert 2 not in flagged, "ユニーク（index 2）は row_indices に含まれないべき"

    def test_duplicate_pair_count_is_two(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """重複ペア（2件だけ同一）の場合、stats['duplicate_count'] が2である。"""
        texts = ["Same text", "Unique alpha", "Same text", "Unique beta"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["duplicate_count"] == 2

    def test_none_mixed_with_duplicate_texts(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """None と重複テキストが混在する場合、重複のみ検出される。"""
        texts = [None, "duplicate", None, "duplicate", "unique"]
        dataset = Dataset.from_dict({"text": texts})
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        flagged = warnings[0].row_indices
        # None（index 0, 2）は検出されない
        assert 0 not in flagged
        assert 2 not in flagged
        # "duplicate"（index 1, 3）は重複として検出される
        assert 1 in flagged
        assert 3 in flagged

    def test_all_same_texts_all_detected(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """全レコードが同一テキストの場合、全件が重複として検出される。"""
        texts = ["same text"] * 4
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["duplicate_count"] == 4
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        for i in range(4):
            assert i in warnings[0].row_indices

    def test_case_sensitive_different_texts_no_duplicates(
        self, checker: ExactDuplicateChecker
    ) -> None:
        """大文字・小文字が異なるテキストは別のテキストとして扱われ、重複なし。"""
        texts = ["Hello world", "hello world", "HELLO WORLD"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["duplicate_count"] == 0
