"""Unit tests for NearDuplicateChecker.

Covers:
- AC-08-01: 近似重複の検出（十分長いテキストで1語のみ変更）
- AC-08-02: 類似度が閾値未満の場合の無検出
- skip_duplicates=True 時のスキップ
- None 値スキップ
- 空データセット
- shingle が空（空文字列）のスキップ
- stats["near_duplicate_count"] の検証
- stats["total_rows"] の検証
- severity=WARNING の検証
- checker_name == "near_duplicate" の検証

テストデータについて:
  MinHash は確率的アルゴリズムのため、近似重複を確実に検出するには
  十分なユニーク shingle 数が必要となる。
  - 近似重複ペア: 87語の自然なテキストで1語のみ変更（真の Jaccard ≈ 0.886）
  - 異なるテキスト: 語彙が完全に重複しないテキスト（Jaccard ≈ 0.0）
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.duplicates import NearDuplicateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity

# --- テストデータ定数 ---
# MinHash の確率的性質を考慮し、十分に長い自然なテキスト（87語）を使用する。
# text_to_shingles(k=5) で 83 個のユニーク shingle を生成し、
# 1語変更後の真の Jaccard ≈ 0.886 (> 閾値 0.8) を保証する。
_LONG_TEXT_DOG = (
    "the quick brown fox jumps over the lazy dog and runs around the park every morning "
    "before the sunrise while eating breakfast and drinking coffee while reading the newspaper "
    "on the front porch of the old farmhouse near the beautiful countryside with rolling hills "
    "and meadows full of colorful flowers swaying in the gentle breeze under the bright blue sky "
    "with white clouds floating slowly through the peaceful and serene landscape where children "
    "play happily in the garden and birds sing melodiously from the tall green trees"
)

# 1語（"dog" → "cat"）のみ変更したテキスト — 真の Jaccard ≈ 0.886
_LONG_TEXT_CAT = _LONG_TEXT_DOG.replace("dog", "cat", 1)

# 語彙が完全に異なるテキスト — Jaccard = 0.0
_DIFFERENT_TEXT = (
    "space exploration galaxy nebula universe planet stellar astronomy telescope "
    "observation cosmic radiation orbit satellite rocket launch mission astronaut "
    "shuttle module crater meteor comet asteroid eclipse solar lunar gravitational "
    "blackhole neutron spectrum wavelength infrared ultraviolet quantum physics "
    "mathematics equation formula laboratory experiment hypothesis theory research "
    "discovery innovation technology engineering computer algorithm programming "
    "database network protocol encryption security cryptography artificial intelligence "
    "machine learning deep learning neural network optimization gradient backpropagation"
)


class TestNearDuplicateChecker:
    """NearDuplicateChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """デフォルト設定（minhash_threshold=0.8, minhash_num_perm=128）。"""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> NearDuplicateChecker:
        """NearDuplicateChecker インスタンス。"""
        return NearDuplicateChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-08-01: 近似重複の検出 ---

    def test_near_duplicates_detected(self, checker: NearDuplicateChecker) -> None:
        """AC-08-01: 1語のみ異なる87語のテキストペアで WARNING が1件発生する。

        真の Jaccard ≈ 0.886 (> 閾値 0.8) のため確実に検出される。
        """
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_CAT])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_near_duplicates_row_indices_contain_pair(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-01: row_indices に類似ペアの少なくとも一方のインデックスが含まれる。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_CAT])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        indices = warnings[0].row_indices
        # 少なくとも一方（index 0 または index 1）が含まれること
        assert 0 in indices or 1 in indices

    def test_near_duplicates_severity_is_warning(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-01: 近似重複検出の Issue の severity が WARNING であること。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_CAT])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.severity == Severity.WARNING

    def test_near_duplicates_with_extra_unique_row(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-01: ユニーク行が混在しても類似ペアのみ検出される。"""
        texts = [
            _LONG_TEXT_DOG,    # index 0: 類似ペアA
            _DIFFERENT_TEXT,   # index 1: 完全に異なる
            _LONG_TEXT_CAT,    # index 2: 類似ペアB
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        # 類似ペア（0と2）が検出される
        assert result.has_issues
        all_flagged: set[int] = set()
        for issue in result.issues:
            all_flagged.update(issue.row_indices)
        # 類似ペアの少なくとも一方（index 0 か index 2）が含まれる
        assert 0 in all_flagged or 2 in all_flagged
        # 完全に異なる index 1 は含まれない
        assert 1 not in all_flagged

    # --- AC-08-02: 類似度が閾値未満の場合の無検出 ---

    def test_different_texts_no_issues(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-02: 互いに大きく異なるテキストでは issues が空リストである。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _DIFFERENT_TEXT])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_multiple_different_texts_no_issues(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-02: 複数の完全に異なるテキストでは issues が空リストである。"""
        texts = [
            "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike",
            "one two three four five six seven eight nine ten eleven twelve thirteen fourteen",
            "monday tuesday wednesday thursday friday saturday sunday morning afternoon evening",
            "red orange yellow green blue indigo violet purple pink black white grey silver gold",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_different_texts_stats_near_duplicate_count_zero(
        self, checker: NearDuplicateChecker
    ) -> None:
        """AC-08-02: 異なるテキストのみの場合、stats['near_duplicate_count'] が0である。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _DIFFERENT_TEXT])
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("near_duplicate_count", 0) == 0

    # --- skip_duplicates=True 時のスキップ ---

    def test_skip_duplicates_no_issues(self) -> None:
        """skip_duplicates=True で類似レコードがあっても Issue なし。"""
        config = CheckerConfig(skip_duplicates=True)
        checker = NearDuplicateChecker(config)

        dataset = Dataset.from_dict({"text": [_LONG_TEXT_DOG, _LONG_TEXT_CAT]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_skip_duplicates_stats_skipped(self) -> None:
        """skip_duplicates=True で stats に 'skipped': True が含まれる。"""
        config = CheckerConfig(skip_duplicates=True)
        checker = NearDuplicateChecker(config)

        dataset = Dataset.from_dict({"text": [_LONG_TEXT_DOG, _LONG_TEXT_CAT]})
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("skipped") is True

    # --- stats の検証 ---

    def test_stats_total_rows(self, checker: NearDuplicateChecker) -> None:
        """stats['total_rows'] がデータセットの行数と一致する。"""
        texts = [_LONG_TEXT_DOG, _DIFFERENT_TEXT, _LONG_TEXT_CAT]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 3

    def test_stats_near_duplicate_count_zero_when_no_duplicates(
        self, checker: NearDuplicateChecker
    ) -> None:
        """近似重複なしの場合、stats['near_duplicate_count'] が0である。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _DIFFERENT_TEXT])
        result = checker.check(dataset, text_field="text")

        assert result.stats["near_duplicate_count"] == 0

    def test_stats_near_duplicate_count_positive_when_duplicates(
        self, checker: NearDuplicateChecker
    ) -> None:
        """近似重複がある場合、stats['near_duplicate_count'] が0より大きい。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_CAT])
        result = checker.check(dataset, text_field="text")

        assert result.stats["near_duplicate_count"] > 0

    # --- エッジケース ---

    def test_empty_dataset(self, checker: NearDuplicateChecker) -> None:
        """空の Dataset では issues が空で near_duplicate_count が0である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["near_duplicate_count"] == 0

    def test_none_values_skipped(self, checker: NearDuplicateChecker) -> None:
        """None 値はスキップされ、近似重複として扱われない。"""
        dataset = Dataset.from_dict({"text": [None, None, _LONG_TEXT_DOG]})
        result = checker.check(dataset, text_field="text")

        # None が2件あるが、スキップされるので検出なし
        assert result.issues == []

    def test_none_mixed_with_similar_texts(
        self, checker: NearDuplicateChecker
    ) -> None:
        """None と類似テキストが混在する場合、None はスキップされ類似ペアのみ検出される。"""
        texts = [
            None,            # index 0: スキップ
            _LONG_TEXT_DOG,  # index 1: 類似ペアA
            None,            # index 2: スキップ
            _LONG_TEXT_CAT,  # index 3: 類似ペアB
        ]
        dataset = Dataset.from_dict({"text": texts})
        result = checker.check(dataset, text_field="text")

        # None はスキップされ、類似ペア（1と3）が検出される
        assert result.has_issues
        all_flagged: set[int] = set()
        for issue in result.issues:
            all_flagged.update(issue.row_indices)
        # None インデックス（0, 2）は含まれない
        assert 0 not in all_flagged
        assert 2 not in all_flagged
        # 類似ペアの少なくとも一方が含まれる
        assert 1 in all_flagged or 3 in all_flagged

    def test_single_record_no_duplicates(
        self, checker: NearDuplicateChecker
    ) -> None:
        """1件のみのデータセットでは近似重複なし。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["near_duplicate_count"] == 0

    def test_empty_string_skipped(self, checker: NearDuplicateChecker) -> None:
        """空文字列は shingle が生成されないためスキップされ、近似重複として扱われない。"""
        texts = ["", "", _LONG_TEXT_DOG]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        # 空文字列はスキップされる
        assert result.issues == []

    # --- checker_name の検証 ---

    def test_checker_name(self, checker: NearDuplicateChecker) -> None:
        """CheckResult.checker_name が 'near_duplicate' であること。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "near_duplicate"

    def test_issue_checker_field_matches_name(
        self, checker: NearDuplicateChecker
    ) -> None:
        """Issue.checker フィールドが 'near_duplicate' と一致すること。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_CAT])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == "near_duplicate"

    # --- カスタム閾値 ---

    def test_high_threshold_rejects_different_texts(self) -> None:
        """高い閾値（0.95）では完全に異なるテキストを検出しない。"""
        config = CheckerConfig(minhash_threshold=0.95)
        checker = NearDuplicateChecker(config)

        dataset = Dataset.from_dict({"text": [_LONG_TEXT_DOG, _DIFFERENT_TEXT]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_exact_same_texts_detected_as_near_duplicate(
        self, checker: NearDuplicateChecker
    ) -> None:
        """完全に同一のテキストは Jaccard=1.0 のため近似重複として検出される。"""
        dataset = self._make_dataset([_LONG_TEXT_DOG, _LONG_TEXT_DOG])
        result = checker.check(dataset, text_field="text")

        # 完全一致は Jaccard=1.0 なので閾値 0.8 を確実に超える
        assert result.has_issues
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
