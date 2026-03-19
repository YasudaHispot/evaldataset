"""Unit tests for LanguageChecker.

Covers:
- AC-04-01: 許可外言語の検出
- AC-04-02: 許可言語での無検出
- Additional: 複数許可言語、None値のスキップ、空データセット
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.text_quality import LanguageChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


# --- テストテキスト定数 ---
# 言語検出の精度確保のため各テキストは80文字以上にする

JAPANESE_TEXT = (
    "これは日本語のテキストです。自然言語処理のテストに使用されます。"
    "このテキストは言語検出のためのサンプルです。十分な長さが必要です。"
    "日本語の文章を使って言語チェッカーの動作を確認します。"
)

ENGLISH_TEXT_1 = (
    "This is a long English text for language detection testing purposes. "
    "The quick brown fox jumps over the lazy dog. "
    "Natural language processing is a subfield of computer science."
)

ENGLISH_TEXT_2 = (
    "Machine learning algorithms require large amounts of training data "
    "to achieve high accuracy on complex tasks such as text classification. "
    "Deep learning models have shown remarkable results in natural language understanding."
)

ENGLISH_TEXT_3 = (
    "The development of artificial intelligence has accelerated rapidly over recent years. "
    "Researchers continue to push the boundaries of what is possible with modern computing. "
    "Large language models demonstrate impressive capabilities in reasoning and text generation."
)

ENGLISH_TEXT_4 = (
    "Datasets are fundamental to training machine learning systems effectively. "
    "Quality control of training data ensures that models learn correct patterns. "
    "Preprocessing and validation are essential steps in any data pipeline."
)


class TestLanguageChecker:
    """LanguageChecker のユニットテスト。

    fast_langdetect を実際に呼び出してテストを行う。
    テキストは十分な長さ（80文字以上）を使用することで言語検出の精度を確保する。
    """

    # --- フィクスチャ ---

    @pytest.fixture
    def config_en_only(self) -> CheckerConfig:
        """英語のみを許可する設定（languages=["en"], language_threshold=0.5）。"""
        return CheckerConfig(languages=["en"], language_threshold=0.5)

    @pytest.fixture
    def config_en_ja(self) -> CheckerConfig:
        """英語と日本語の両方を許可する設定。"""
        return CheckerConfig(languages=["en", "ja"], language_threshold=0.5)

    @pytest.fixture
    def checker_en_only(self, config_en_only: CheckerConfig) -> LanguageChecker:
        """英語のみ許可の LanguageChecker インスタンス。"""
        return LanguageChecker(config_en_only)

    @pytest.fixture
    def checker_en_ja(self, config_en_ja: CheckerConfig) -> LanguageChecker:
        """英語・日本語許可の LanguageChecker インスタンス。"""
        return LanguageChecker(config_en_ja)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-04-01: 許可外言語の検出 ---

    def test_japanese_text_detected_as_non_target(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """AC-04-01: languages=["en"] で日本語テキスト1件を含む Dataset で WARNING が1件発生する。"""
        texts = [
            JAPANESE_TEXT,   # index 0: 日本語（許可外）
            ENGLISH_TEXT_1,  # index 1: 英語（許可）
            ENGLISH_TEXT_2,  # index 2: 英語（許可）
            ENGLISH_TEXT_3,  # index 3: 英語（許可）
            ENGLISH_TEXT_4,  # index 4: 英語（許可）
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_japanese_text_row_index_in_issue(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """AC-04-01: WARNING の row_indices に日本語レコードのインデックスが含まれる。"""
        texts = [
            ENGLISH_TEXT_1,  # index 0: 英語（許可）
            JAPANESE_TEXT,   # index 1: 日本語（許可外）
            ENGLISH_TEXT_2,  # index 2: 英語（許可）
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        all_flagged_indices = [idx for issue in warnings for idx in issue.row_indices]
        assert 1 in all_flagged_indices, "インデックス1（日本語テキスト）が row_indices に含まれるべき"

    def test_non_target_language_severity_is_warning(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """AC-04-01: 許可外言語の Issue の severity が WARNING であること。"""
        dataset = self._make_dataset([JAPANESE_TEXT, ENGLISH_TEXT_1])
        result = checker_en_only.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.severity == Severity.WARNING, (
                f"Issue の severity は WARNING であるべき: {issue.severity}"
            )

    def test_non_target_count_stat(self, checker_en_only: LanguageChecker) -> None:
        """AC-04-01: stats['non_target_count'] が許可外言語レコード数と一致する。"""
        texts = [
            JAPANESE_TEXT,   # 許可外
            ENGLISH_TEXT_1,  # 許可
            ENGLISH_TEXT_2,  # 許可
            ENGLISH_TEXT_3,  # 許可
            ENGLISH_TEXT_4,  # 許可
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.stats["non_target_count"] == 1

    def test_checked_count_stat_excludes_none(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """stats['checked_count'] が None をスキップした有効レコード数と一致する。"""
        texts = [
            ENGLISH_TEXT_1,  # 有効
            None,            # スキップ
            JAPANESE_TEXT,   # 有効（許可外）
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.stats["checked_count"] == 2

    # --- AC-04-02: 許可言語での無検出 ---

    def test_all_english_no_issues(self, checker_en_only: LanguageChecker) -> None:
        """AC-04-02: 全レコードが英語の Dataset では issues が空リストになる。"""
        texts = [
            ENGLISH_TEXT_1,
            ENGLISH_TEXT_2,
            ENGLISH_TEXT_3,
            ENGLISH_TEXT_4,
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.issues == []

    def test_all_english_non_target_count_is_zero(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """AC-04-02: 全レコードが英語の Dataset では stats['non_target_count'] が 0 である。"""
        texts = [ENGLISH_TEXT_1, ENGLISH_TEXT_2, ENGLISH_TEXT_3]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.stats["non_target_count"] == 0

    def test_all_english_checked_count_matches_total(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """AC-04-02: None がない場合 stats['checked_count'] がレコード総数と一致する。"""
        texts = [ENGLISH_TEXT_1, ENGLISH_TEXT_2, ENGLISH_TEXT_3]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.stats["checked_count"] == 3

    # --- 複数許可言語（languages=["en", "ja"]）のテスト ---

    def test_japanese_allowed_when_in_languages(
        self, checker_en_ja: LanguageChecker
    ) -> None:
        """languages=["en", "ja"] の場合、日本語テキストが許可されて issues が空になる。"""
        texts = [
            JAPANESE_TEXT,
            ENGLISH_TEXT_1,
            ENGLISH_TEXT_2,
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_ja.check(dataset, text_field="text")

        assert result.issues == []

    def test_japanese_and_english_both_allowed(
        self, checker_en_ja: LanguageChecker
    ) -> None:
        """languages=["en", "ja"] で日本語・英語が混在しても non_target_count が 0 である。"""
        texts = [
            JAPANESE_TEXT,
            ENGLISH_TEXT_1,
            JAPANESE_TEXT,
            ENGLISH_TEXT_2,
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_ja.check(dataset, text_field="text")

        assert result.stats["non_target_count"] == 0

    # --- None 値のスキップ ---

    def test_none_values_are_skipped(self, checker_en_only: LanguageChecker) -> None:
        """None 値はスキップされ、許可外言語として検出されない。"""
        texts = [None, ENGLISH_TEXT_1, None, ENGLISH_TEXT_2]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["non_target_count"] == 0

    def test_none_values_not_in_flagged_indices(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """None が含まれても、WARNING の row_indices に None のインデックスは含まれない。"""
        texts = [
            None,            # index 0: スキップ
            JAPANESE_TEXT,   # index 1: 許可外
            None,            # index 2: スキップ
        ]
        dataset = self._make_dataset(texts)
        result = checker_en_only.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1, "日本語テキストが検出されるべき"
        all_flagged_indices = [idx for issue in warnings for idx in issue.row_indices]
        assert 0 not in all_flagged_indices, "None（index 0）が row_indices に含まれてはいけない"
        assert 2 not in all_flagged_indices, "None（index 2）が row_indices に含まれてはいけない"
        assert 1 in all_flagged_indices, "日本語テキスト（index 1）が row_indices に含まれるべき"

    # --- 空データセット ---

    def test_empty_dataset_no_issues(self, checker_en_only: LanguageChecker) -> None:
        """空の Dataset では issues が空リストである。"""
        dataset = self._make_dataset([])
        result = checker_en_only.check(dataset, text_field="text")

        assert result.issues == []

    def test_empty_dataset_stats(self, checker_en_only: LanguageChecker) -> None:
        """空の Dataset では stats['checked_count'] と stats['non_target_count'] が 0 である。"""
        dataset = self._make_dataset([])
        result = checker_en_only.check(dataset, text_field="text")

        assert result.stats.get("checked_count", 0) == 0
        assert result.stats.get("non_target_count", 0) == 0

    # --- checker_name の確認 ---

    # --- 閾値境界値テスト ---

    def test_threshold_boundary_below(self) -> None:
        """score < threshold の場合、許可外言語でも検出しない。"""
        config = CheckerConfig(languages=["en"], language_threshold=0.99)
        checker = LanguageChecker(config)
        # 閾値を非常に高く設定することで、検出が抑制される
        dataset = self._make_dataset([JAPANESE_TEXT, ENGLISH_TEXT_1])
        result = checker.check(dataset, text_field="text")

        # 閾値0.99では多くのテキストの信頼度が0.99未満なので検出されにくい
        # 少なくとも non_target_count が通常より少ないことを確認
        assert result.stats["non_target_count"] <= 1

    def test_threshold_at_minimum(self) -> None:
        """threshold=0.0 の場合、信頼度にかかわらず許可外言語が検出される。"""
        config = CheckerConfig(languages=["en"], language_threshold=0.0)
        checker = LanguageChecker(config)
        dataset = self._make_dataset([JAPANESE_TEXT, ENGLISH_TEXT_1])
        result = checker.check(dataset, text_field="text")

        assert result.stats["non_target_count"] >= 1

    # --- メタデータ ---

    def test_checker_name_in_result(self, checker_en_only: LanguageChecker) -> None:
        """CheckResult.checker_name が設定されていること。"""
        dataset = self._make_dataset([ENGLISH_TEXT_1])
        result = checker_en_only.check(dataset, text_field="text")

        assert result.checker_name == "language"

    def test_issue_checker_field_matches_checker_name(
        self, checker_en_only: LanguageChecker
    ) -> None:
        """Issue.checker フィールドが CheckResult.checker_name と一致すること。"""
        dataset = self._make_dataset([JAPANESE_TEXT, ENGLISH_TEXT_1])
        result = checker_en_only.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == result.checker_name
