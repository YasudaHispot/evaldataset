"""Unit tests for RowFilter.

Covers:
- AC-16-01: 完全一致重複行の除去（ExactDuplicateChecker の CheckResult に基づく）
- AC-16-02: 近似重複行の除去（NearDuplicateChecker の CheckResult に基づく）
- AC-16-03: 短文/長文行のフィルタリング（TextLengthChecker の CheckResult に基づく）
- AC-16-04: skip_checkers によるフィルタスキップ
- 複数チェッカーの結果統合
- 重複インデックスの union（重複なし除去）
- FILTER_CHECKERS 以外のチェッカー結果は無視
- 空の check_results では行数変化なし
- 全行が除去対象になるケース
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.models import CheckResult, Issue, Severity


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_dataset(texts: list[str]) -> Dataset:
    """テスト用 Dataset を作成する。"""
    return Dataset.from_dict({"text": texts})


def _make_check_result(
    checker_name: str,
    row_indices: list[int],
    severity: Severity = Severity.WARNING,
) -> CheckResult:
    """Issue を 1 件持つ CheckResult を生成する。"""
    issue = Issue(
        checker=checker_name,
        severity=severity,
        message=f"test issue from {checker_name}",
        row_indices=row_indices,
    )
    return CheckResult(checker_name=checker_name, issues=[issue])


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def row_filter():
    """RowFilter インスタンスを返す。"""
    from evaldataset.fixer import RowFilter

    return RowFilter()


@pytest.fixture
def five_row_dataset() -> Dataset:
    """5 行のテスト用 Dataset。"""
    return _make_dataset(
        [
            "unique text alpha",
            "duplicate text",
            "unique text beta",
            "duplicate text",
            "unique text gamma",
        ]
    )


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestRowFilterBasic:
    """RowFilter の基本動作テスト。"""

    def test_filter_dataset_returns_tuple(self, row_filter, five_row_dataset) -> None:
        """filter_dataset は (Dataset, dict) のタプルを返す。"""
        result = row_filter.filter_dataset(five_row_dataset, check_results=[])
        assert isinstance(result, tuple)
        assert len(result) == 2
        filtered_dataset, filter_stats = result
        assert isinstance(filtered_dataset, Dataset)
        assert isinstance(filter_stats, dict)

    def test_filter_stats_has_required_keys(self, row_filter, five_row_dataset) -> None:
        """filter_stats に必要なキーが全て含まれる。"""
        _, filter_stats = row_filter.filter_dataset(five_row_dataset, check_results=[])
        expected_keys = {
            "exact_duplicate",
            "near_duplicate",
            "text_length",
            "pii",
            "total_rows_removed",
            "rows_after_filter",
        }
        assert expected_keys.issubset(filter_stats.keys())

    def test_filter_checkers_constant_defined(self, row_filter) -> None:
        """FILTER_CHECKERS 定数が正しく定義されている。"""
        from evaldataset.fixer import RowFilter

        assert hasattr(RowFilter, "FILTER_CHECKERS")
        assert "exact_duplicate" in RowFilter.FILTER_CHECKERS
        assert "near_duplicate" in RowFilter.FILTER_CHECKERS
        assert "text_length" in RowFilter.FILTER_CHECKERS
        assert "pii" in RowFilter.FILTER_CHECKERS


class TestRowFilterEmptyCheckResults:
    """check_results が空のケース。"""

    def test_empty_check_results_no_rows_removed(
        self, row_filter, five_row_dataset
    ) -> None:
        """check_results が空のとき、行数が変化しない。"""
        # AC-16-01 前提: チェッカー結果がない場合
        filtered_dataset, _ = row_filter.filter_dataset(
            five_row_dataset, check_results=[]
        )
        assert len(filtered_dataset) == len(five_row_dataset)

    def test_empty_check_results_all_stats_zero(
        self, row_filter, five_row_dataset
    ) -> None:
        """check_results が空のとき、全 stats が 0。"""
        _, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=[]
        )
        assert filter_stats["exact_duplicate"] == 0
        assert filter_stats["near_duplicate"] == 0
        assert filter_stats["text_length"] == 0
        assert filter_stats["pii"] == 0
        assert filter_stats["total_rows_removed"] == 0

    def test_empty_check_results_rows_after_filter_equals_original(
        self, row_filter, five_row_dataset
    ) -> None:
        """check_results が空のとき、rows_after_filter が元の行数に等しい。"""
        _, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=[]
        )
        assert filter_stats["rows_after_filter"] == len(five_row_dataset)


class TestRowFilterExactDuplicate:
    """AC-16-01: ExactDuplicateChecker の結果に基づく除去。"""

    def test_exact_duplicate_rows_removed(self, row_filter, five_row_dataset) -> None:
        """AC-16-01: exact_duplicate の row_indices=[1,3] → filter後3行。"""
        # Given: 5行のDataset + ExactDuplicateChecker の CheckResult（row_indices=[1,3]）
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        # When: filter_dataset を実行する
        filtered_dataset, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=check_results
        )

        # Then: filter後3行
        assert len(filtered_dataset) == 3

    def test_exact_duplicate_stat_recorded(
        self, row_filter, five_row_dataset
    ) -> None:
        """AC-16-01: filter_stats の exact_duplicate が除去数と一致する。"""
        # Given: ExactDuplicateChecker が row_indices=[1,3] を報告
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        # When
        _, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=check_results
        )

        # Then: exact_duplicate == 2
        assert filter_stats["exact_duplicate"] == 2

    def test_exact_duplicate_total_rows_removed(
        self, row_filter, five_row_dataset
    ) -> None:
        """AC-16-01: total_rows_removed が除去された実際の行数と一致する。"""
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]
        _, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=check_results
        )
        assert filter_stats["total_rows_removed"] == 2

    def test_exact_duplicate_rows_after_filter(
        self, row_filter, five_row_dataset
    ) -> None:
        """AC-16-01: rows_after_filter が元の行数 - 除去数と一致する。"""
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]
        _, filter_stats = row_filter.filter_dataset(
            five_row_dataset, check_results=check_results
        )
        assert filter_stats["rows_after_filter"] == 3

    def test_exact_duplicate_remaining_rows_content(
        self, row_filter, five_row_dataset
    ) -> None:
        """AC-16-01: 除去されない行のテキストが保持される。"""
        # インデックス 1, 3 が除去され、0, 2, 4 が残る
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]
        filtered_dataset, _ = row_filter.filter_dataset(
            five_row_dataset, check_results=check_results
        )
        remaining_texts = filtered_dataset["text"]
        assert "unique text alpha" in remaining_texts
        assert "unique text beta" in remaining_texts
        assert "unique text gamma" in remaining_texts
        assert "duplicate text" not in remaining_texts


class TestRowFilterMultipleCheckers:
    """複数チェッカーの結果統合テスト。"""

    def test_multiple_checkers_non_overlapping_indices_combined(
        self, row_filter
    ) -> None:
        """複数チェッカーの非重複インデックスが統合されて除去される。

        exact_duplicate(row_indices=[1]) + text_length(row_indices=[2,3])
        → 重複なしで3行除去（5行→2行）
        """
        dataset = _make_dataset(
            [
                "text row 0",
                "duplicate text",
                "short",
                "short again",
                "text row 4",
            ]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1]),
            _make_check_result("text_length", row_indices=[2, 3]),
        ]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # 3行除去 → 2行残る
        assert len(filtered_dataset) == 2
        assert filter_stats["exact_duplicate"] == 1
        assert filter_stats["text_length"] == 2
        assert filter_stats["total_rows_removed"] == 3

    def test_multiple_checkers_stats_per_checker(self, row_filter) -> None:
        """複数チェッカーの stats が各チェッカー名ごとに記録される。"""
        dataset = _make_dataset(
            ["text row 0", "dup text", "short", "short too", "text row 4"]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1]),
            _make_check_result("text_length", row_indices=[2, 3]),
            _make_check_result("pii", row_indices=[]),
        ]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert filter_stats["exact_duplicate"] == 1
        assert filter_stats["text_length"] == 2
        assert filter_stats["pii"] == 0
        assert filter_stats["near_duplicate"] == 0


class TestRowFilterIndexUnion:
    """重複インデックスの union テスト。"""

    def test_overlapping_indices_counted_once(self, row_filter) -> None:
        """AC-16-01/AC-16-03: 重複インデックスが union で 1 回だけ除去される。

        exact_duplicate(row_indices=[1,2]) + text_length(row_indices=[2,3])
        → union{1,2,3} で 3 行除去（5行→2行）
        """
        dataset = _make_dataset(
            [
                "text row 0",
                "duplicate text",
                "short dup",  # exact_duplicate と text_length 両方に該当
                "short text",
                "text row 4",
            ]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1, 2]),
            _make_check_result("text_length", row_indices=[2, 3]),
        ]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # union{1,2,3} = 3行除去 → 2行残る
        assert len(filtered_dataset) == 2

    def test_overlapping_indices_total_rows_removed_no_double_count(
        self, row_filter
    ) -> None:
        """重複インデックスが total_rows_removed でダブルカウントされない。

        インデックス 2 が exact_duplicate と text_length 両方に含まれても
        total_rows_removed は 3（union のサイズ）になる。
        """
        dataset = _make_dataset(
            [
                "text row 0",
                "duplicate text",
                "short dup",
                "short text",
                "text row 4",
            ]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1, 2]),
            _make_check_result("text_length", row_indices=[2, 3]),
        ]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # union{1,2,3} = 3行除去
        assert filter_stats["total_rows_removed"] == 3

    def test_overlapping_indices_per_checker_stat_not_deduplicated(
        self, row_filter
    ) -> None:
        """各チェッカーの stat は自身が報告したインデックス数を記録する（union しない）。

        exact_duplicate が 2 件、text_length が 2 件（うち 1 件重複）の場合、
        各チェッカーの stat はそれぞれ 2 になる。
        """
        dataset = _make_dataset(
            [
                "text row 0",
                "duplicate text",
                "short dup",
                "short text",
                "text row 4",
            ]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1, 2]),
            _make_check_result("text_length", row_indices=[2, 3]),
        ]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert filter_stats["exact_duplicate"] == 2
        assert filter_stats["text_length"] == 2


class TestRowFilterIgnoresNonFilterCheckers:
    """FILTER_CHECKERS 以外のチェッカー結果を無視するテスト。"""

    def test_language_checker_result_ignored(self, row_filter) -> None:
        """FILTER_CHECKERS に含まれない language チェッカーの結果は無視される。"""
        dataset = _make_dataset(
            ["english text", "japanese text", "another english", "more text", "last"]
        )
        # language チェッカーが行 1 を問題と報告
        check_results = [_make_check_result("language", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # language は FILTER_CHECKERS に含まれないので除去されない
        assert len(filtered_dataset) == 5
        assert filter_stats["total_rows_removed"] == 0

    def test_schema_checker_result_ignored(self, row_filter) -> None:
        """schema チェッカーの結果は無視される（FILTER_CHECKERS に含まれない）。"""
        dataset = _make_dataset(["text a", "text b", "text c"])
        check_results = [_make_check_result("schema", row_indices=[0, 1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["total_rows_removed"] == 0

    def test_non_filter_checker_does_not_appear_in_stats(self, row_filter) -> None:
        """FILTER_CHECKERS 以外のチェッカー名は filter_stats のキーに現れない。"""
        dataset = _make_dataset(["text a", "text b"])
        check_results = [_make_check_result("language", row_indices=[0])]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert "language" not in filter_stats

    def test_mixed_filter_and_non_filter_checkers(self, row_filter) -> None:
        """FILTER_CHECKERS とそれ以外が混在する場合、FILTER_CHECKERS の結果のみ適用。"""
        dataset = _make_dataset(
            ["text row 0", "dup text", "foreign text", "short", "text row 4"]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1]),  # 除去対象
            _make_check_result("language", row_indices=[2]),  # 無視
            _make_check_result("text_length", row_indices=[3]),  # 除去対象
        ]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # exact_duplicate(1) + text_length(3) = 2行除去
        assert len(filtered_dataset) == 3
        assert filter_stats["total_rows_removed"] == 2


class TestRowFilterNearDuplicate:
    """AC-16-02: NearDuplicateChecker の結果に基づく除去。"""

    def test_near_duplicate_rows_removed(self, row_filter) -> None:
        """AC-16-02: near_duplicate の row_indices に基づく除去。"""
        dataset = _make_dataset(
            [
                "The quick brown fox",
                "The quick brown fox jumps",  # 近似重複（除去対象）
                "Completely different text",
                "Another unique document",
                "Final unique text",
            ]
        )
        check_results = [_make_check_result("near_duplicate", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 4
        assert filter_stats["near_duplicate"] == 1
        assert filter_stats["total_rows_removed"] == 1

    def test_near_duplicate_stat_in_filter_stats(self, row_filter) -> None:
        """AC-16-02: filter_stats に near_duplicate が記録される。"""
        dataset = _make_dataset(["text a", "text b near dup", "text c", "text d"])
        check_results = [_make_check_result("near_duplicate", row_indices=[1])]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert "near_duplicate" in filter_stats
        assert filter_stats["near_duplicate"] == 1


class TestRowFilterTextLength:
    """AC-16-03: TextLengthChecker の結果に基づく除去。"""

    def test_short_text_rows_removed(self, row_filter) -> None:
        """AC-16-03: 短文行が除去され、出力 Dataset の行数が減る。"""
        dataset = _make_dataset(
            [
                "This is a normal length text that should be kept.",
                "Hi",  # 短文（除去対象）
                "Another normal length text for the dataset.",
            ]
        )
        check_results = [_make_check_result("text_length", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # 短文行が除去され 2 行になる
        assert len(filtered_dataset) == 2
        assert filter_stats["text_length"] == 1
        assert filter_stats["total_rows_removed"] == 1

    def test_short_text_rows_content_verified(self, row_filter) -> None:
        """AC-16-03: 短文行が除去され、残った行のコンテンツが正しい。"""
        dataset = _make_dataset(
            [
                "Normal text for row 0",
                "Hi",  # 短文
                "Normal text for row 2",
            ]
        )
        check_results = [_make_check_result("text_length", row_indices=[1])]

        filtered_dataset, _ = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        remaining_texts = filtered_dataset["text"]
        assert "Normal text for row 0" in remaining_texts
        assert "Normal text for row 2" in remaining_texts
        assert "Hi" not in remaining_texts

    def test_long_text_rows_removed(self, row_filter) -> None:
        """AC-16-03: 長文行も text_length チェッカーの結果に基づいて除去される。"""
        dataset = _make_dataset(
            [
                "Normal text",
                "x" * 200000,  # 長文（除去対象）
                "Another normal text",
            ]
        )
        check_results = [_make_check_result("text_length", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 2
        assert filter_stats["text_length"] == 1


class TestRowFilterAllRowsRemoved:
    """全行が除去対象になるエッジケース。"""

    def test_all_rows_removed_returns_empty_dataset(self, row_filter) -> None:
        """全行のインデックスが含まれる場合、0 行の Dataset が返される。"""
        dataset = _make_dataset(["dup text", "dup text", "dup text"])
        check_results = [_make_check_result("exact_duplicate", row_indices=[0, 1, 2])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 0
        assert filter_stats["total_rows_removed"] == 3
        assert filter_stats["rows_after_filter"] == 0

    def test_all_rows_removed_stats_correct(self, row_filter) -> None:
        """全行除去時の stats が正しく記録される。"""
        dataset = _make_dataset(["short", "hi", "ok"])
        check_results = [_make_check_result("text_length", row_indices=[0, 1, 2])]

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert filter_stats["text_length"] == 3
        assert filter_stats["total_rows_removed"] == 3
        assert filter_stats["rows_after_filter"] == 0


class TestRowFilterSkipCheckers:
    """AC-16-04: skip_checkers によるフィルタスキップ。"""

    def test_skip_exact_duplicate_does_not_remove_rows(self, row_filter) -> None:
        """AC-16-04: skip_checkers=['exact_duplicate'] で重複行が除去されない。"""
        # Given: 重複行を含む Dataset と skip_checkers=['exact_duplicate']
        dataset = _make_dataset(
            [
                "unique text",
                "duplicate text",
                "another unique",
                "duplicate text",
                "last unique",
            ]
        )
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        # When: skip_checkers に exact_duplicate を指定して実行
        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset,
            check_results=check_results,
            skip_checkers=["exact_duplicate"],
        )

        # Then: 重複行が除去されず、行数が元のまま
        assert len(filtered_dataset) == 5
        assert filter_stats["exact_duplicate"] == 0
        assert filter_stats["total_rows_removed"] == 0

    def test_skip_text_length_does_not_remove_short_rows(self, row_filter) -> None:
        """AC-16-04: skip_checkers=['text_length'] で短文行が除去されない。"""
        dataset = _make_dataset(["normal text", "hi", "another normal text"])
        check_results = [_make_check_result("text_length", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset,
            check_results=check_results,
            skip_checkers=["text_length"],
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["text_length"] == 0
        assert filter_stats["total_rows_removed"] == 0

    def test_skip_one_checker_allows_other_to_filter(self, row_filter) -> None:
        """AC-16-04: 1 つをスキップしても他のチェッカーは有効のまま。"""
        dataset = _make_dataset(
            ["normal text", "duplicate", "short", "duplicate", "normal text 2"]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1, 3]),
            _make_check_result("text_length", row_indices=[2]),
        ]

        # exact_duplicate をスキップ、text_length は有効
        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset,
            check_results=check_results,
            skip_checkers=["exact_duplicate"],
        )

        # text_length の対象（行 2）のみ除去 → 4 行残る
        assert len(filtered_dataset) == 4
        assert filter_stats["exact_duplicate"] == 0
        assert filter_stats["text_length"] == 1
        assert filter_stats["total_rows_removed"] == 1

    def test_skip_multiple_checkers(self, row_filter) -> None:
        """AC-16-04: 複数チェッカーを skip_checkers で一括スキップ。"""
        dataset = _make_dataset(
            ["normal", "duplicate", "short", "duplicate", "ok"]
        )
        check_results = [
            _make_check_result("exact_duplicate", row_indices=[1, 3]),
            _make_check_result("text_length", row_indices=[2]),
        ]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset,
            check_results=check_results,
            skip_checkers=["exact_duplicate", "text_length"],
        )

        # 全てスキップ → 元の行数のまま
        assert len(filtered_dataset) == 5
        assert filter_stats["total_rows_removed"] == 0

    def test_skip_checkers_default_is_none_or_empty(self, row_filter) -> None:
        """skip_checkers を省略したとき（デフォルト）は全チェッカーが有効。"""
        dataset = _make_dataset(["normal text", "dup", "normal text 2", "dup", "ok"])
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        # skip_checkers を省略
        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["total_rows_removed"] == 2

    def test_skip_non_filter_checker_has_no_effect(self, row_filter) -> None:
        """FILTER_CHECKERS に含まれないチェッカーを skip_checkers に指定しても動作に影響しない。"""
        dataset = _make_dataset(["text a", "dup text", "text b", "dup text", "text c"])
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        # language は元々 FILTER_CHECKERS に含まれないので、スキップしても結果は変わらない
        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset,
            check_results=check_results,
            skip_checkers=["language"],  # FILTER_CHECKERS 外を指定
        )

        # exact_duplicate は有効のまま → 2 行除去
        assert len(filtered_dataset) == 3
        assert filter_stats["total_rows_removed"] == 2


class TestRowFilterPii:
    """PiiChecker の結果に基づく除去テスト。"""

    def test_pii_rows_removed(self, row_filter) -> None:
        """PII を含む行が filter_dataset で除去される。"""
        dataset = _make_dataset(
            [
                "Normal text without PII",
                "Contact me at user@example.com for details",  # PII（除去対象）
                "Another normal text",
                "More content here",
            ]
        )
        check_results = [_make_check_result("pii", row_indices=[1])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["pii"] == 1
        assert filter_stats["total_rows_removed"] == 1

    def test_pii_stat_zero_when_no_pii_issues(self, row_filter) -> None:
        """PII チェッカーの結果がない場合、pii stat が 0。"""
        dataset = _make_dataset(["text a", "text b"])
        check_results = []

        _, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert filter_stats["pii"] == 0


class TestRowFilterIssuesWithoutRowIndices:
    """row_indices が空の Issue を持つ CheckResult のテスト。"""

    def test_issue_with_empty_row_indices_removes_nothing(self, row_filter) -> None:
        """row_indices が空の Issue は何も除去しない。"""
        dataset = _make_dataset(["text a", "text b", "text c"])
        check_results = [_make_check_result("exact_duplicate", row_indices=[])]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["exact_duplicate"] == 0
        assert filter_stats["total_rows_removed"] == 0

    def test_check_result_without_issues_removes_nothing(self, row_filter) -> None:
        """Issue を持たない CheckResult は何も除去しない。"""
        dataset = _make_dataset(["text a", "text b", "text c"])
        # Issues が空の CheckResult
        check_result = CheckResult(checker_name="exact_duplicate", issues=[])
        check_results = [check_result]

        filtered_dataset, filter_stats = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        assert len(filtered_dataset) == 3
        assert filter_stats["total_rows_removed"] == 0


class TestRowFilterPreservesNonTextColumns:
    """テキスト以外の列が保持されることを確認するテスト。"""

    def test_non_text_columns_preserved_after_filter(self, row_filter) -> None:
        """フィルタ後も text 以外の列（id, label 等）が保持される。"""
        dataset = Dataset.from_dict(
            {
                "text": ["text row 0", "dup text", "text row 2", "dup text", "text row 4"],
                "id": [0, 1, 2, 3, 4],
                "label": ["a", "b", "c", "d", "e"],
            }
        )
        check_results = [_make_check_result("exact_duplicate", row_indices=[1, 3])]

        filtered_dataset, _ = row_filter.filter_dataset(
            dataset, check_results=check_results
        )

        # id と label が保持されること
        assert "id" in filtered_dataset.column_names
        assert "label" in filtered_dataset.column_names
        # 除去されなかった行の id が正しい
        assert set(filtered_dataset["id"]) == {0, 2, 4}
