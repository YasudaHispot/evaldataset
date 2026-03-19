"""Unit tests for MojibakeChecker.

Covers:
- AC-06-01: 文字化けテキストの検出（ftfy.fix_text で変化するテキストで WARNING）
- AC-06-02: 正常テキストでの無検出
- 複数レコード混在（文字化け+正常）
- 境界値: ftfy による正規化のみで変わるテキスト（全角スペース、BOM等）
- 空データセット
- None値スキップ
- 例外スキップ（has_mojibake が例外を投げた場合）
- stats["mojibake_count"] の検証
- stats["total_rows"] の検証
- severity=WARNING の検証
- checker_name == "mojibake" の検証
- レジストリへの登録確認
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.text_quality import MojibakeChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


# --- テストテキスト定数 ---

# ftfy.fix_text で修正される典型的な文字化けテキスト
# UTF-8をWindows-1252として誤解釈した場合に出現するパターン
# "hello" を囲む左右の引用符が化けた文字列 → "hello"
MOJIBAKE_TEXT = "\u00e2\u0080\u009chello\u00e2\u0080\u009d"

# é が Ã© として化けたテキスト → é
MOJIBAKE_ACCENTED = "\u00c3\u00a9"

# 別の引用符文字化けパターン
MOJIBAKE_ALT_QUOTES = "\u00e2\u20ac\u009chello\u00e2\u20ac\u009d"

# 正常なUTF-8テキスト（ftfy.fix_textで変化しない）
NORMAL_TEXT_1 = "This is a perfectly normal English text without any encoding issues."
NORMAL_TEXT_2 = "Another clean text with proper UTF-8 encoding and no garbled characters."
NORMAL_TEXT_3 = "The quick brown fox jumps over the lazy dog."


class TestMojibakeChecker:
    """MojibakeChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> MojibakeChecker:
        return MojibakeChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    @staticmethod
    def _get_warning_indices(result) -> list[int]:
        """CheckResult から WARNING の row_indices を全件取得する。"""
        return [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ]

    # --- AC-06-01: 文字化けテキストの検出 ---

    def test_mojibake_text_detected(self, checker: MojibakeChecker) -> None:
        """AC-06-01: 文字化けテキストを含むデータセットで WARNING が1件以上発生する。"""
        dataset = self._make_dataset([MOJIBAKE_TEXT, NORMAL_TEXT_1])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_mojibake_text_row_index_in_issue(self, checker: MojibakeChecker) -> None:
        """AC-06-01: WARNING の row_indices に文字化けレコードのインデックスが含まれる。"""
        # index 0: 正常, index 1: 文字化け, index 2: 正常
        dataset = self._make_dataset([NORMAL_TEXT_1, MOJIBAKE_TEXT, NORMAL_TEXT_2])
        result = checker.check(dataset, text_field="text")

        all_flagged_indices = self._get_warning_indices(result)
        assert 1 in all_flagged_indices, "文字化けレコード（index 1）が row_indices に含まれるべき"
        assert 0 not in all_flagged_indices, "正常レコード（index 0）は row_indices に含まれないべき"
        assert 2 not in all_flagged_indices, "正常レコード（index 2）は row_indices に含まれないべき"

    def test_mojibake_severity_is_warning(self, checker: MojibakeChecker) -> None:
        """AC-06-01: 文字化け Issue の severity が WARNING であること。"""
        dataset = self._make_dataset([MOJIBAKE_TEXT])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "文字化けテキストで Issue が発生するべき"
        for issue in result.issues:
            assert issue.severity == Severity.WARNING

    def test_mojibake_count_stat(self, checker: MojibakeChecker) -> None:
        """AC-06-01: stats['mojibake_count'] が文字化けレコード数と一致する（1件）。"""
        dataset = self._make_dataset([MOJIBAKE_TEXT, NORMAL_TEXT_1, NORMAL_TEXT_2])
        result = checker.check(dataset, text_field="text")

        assert result.stats["mojibake_count"] == 1

    def test_total_rows_stat(self, checker: MojibakeChecker) -> None:
        """stats['total_rows'] がデータセットの全行数と一致する。"""
        dataset = self._make_dataset([MOJIBAKE_TEXT, NORMAL_TEXT_1, NORMAL_TEXT_2])
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 3

    def test_various_mojibake_patterns_detected(self, checker: MojibakeChecker) -> None:
        """AC-06-01: 複数パターンの文字化けテキストが全て検出される。"""
        dataset = self._make_dataset([
            MOJIBAKE_TEXT,
            MOJIBAKE_ACCENTED,
            MOJIBAKE_ALT_QUOTES,
        ])
        result = checker.check(dataset, text_field="text")

        assert result.stats["mojibake_count"] == 3

    # --- AC-06-02: 正常テキストでの無検出 ---

    def test_normal_text_no_issues(self, checker: MojibakeChecker) -> None:
        """AC-06-02: 正常UTF-8テキストのみの Dataset では issues が空リストになる。"""
        dataset = self._make_dataset([NORMAL_TEXT_1, NORMAL_TEXT_2, NORMAL_TEXT_3])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_normal_text_mojibake_count_is_zero(self, checker: MojibakeChecker) -> None:
        """AC-06-02: 正常テキストでは stats['mojibake_count'] が 0 である。"""
        dataset = self._make_dataset([NORMAL_TEXT_1, NORMAL_TEXT_2])
        result = checker.check(dataset, text_field="text")

        assert result.stats["mojibake_count"] == 0

    def test_normal_accented_chars_not_detected(self, checker: MojibakeChecker) -> None:
        """AC-06-02: 正しくエンコードされたアクセント文字（é）は文字化けとして検出されない。"""
        # U+00E9 は正しい UTF-8 エンコードのアクセント文字（é）
        accented_text = "Caf\u00e9 au lait with proper encoding is fine."
        dataset = self._make_dataset([accented_text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["mojibake_count"] == 0

    # --- 複数レコード混在 ---

    def test_mixed_mojibake_and_clean_texts_detection(
        self, checker: MojibakeChecker
    ) -> None:
        """複数レコード混在: 文字化けレコードのみ検出され、正常レコードは検出されない。"""
        texts = [
            NORMAL_TEXT_1,    # index 0: 正常
            MOJIBAKE_TEXT,    # index 1: 文字化け
            NORMAL_TEXT_2,    # index 2: 正常
            MOJIBAKE_ACCENTED, # index 3: 文字化け
            NORMAL_TEXT_3,    # index 4: 正常
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warning_indices = self._get_warning_indices(result)
        assert 1 in warning_indices, "文字化けレコード（index 1）が検出されるべき"
        assert 3 in warning_indices, "文字化けレコード（index 3）が検出されるべき"
        assert 0 not in warning_indices, "正常レコード（index 0）は検出されないべき"
        assert 2 not in warning_indices, "正常レコード（index 2）は検出されないべき"
        assert 4 not in warning_indices, "正常レコード（index 4）は検出されないべき"

    def test_mixed_records_mojibake_count(self, checker: MojibakeChecker) -> None:
        """複数レコード混在: mojibake_count が文字化けレコード数と正確に一致する。"""
        texts = [
            NORMAL_TEXT_1,     # index 0: 正常
            MOJIBAKE_TEXT,     # index 1: 文字化け
            NORMAL_TEXT_2,     # index 2: 正常
            MOJIBAKE_ACCENTED, # index 3: 文字化け
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["mojibake_count"] == 2

    # --- 境界値: 正規化のみで変わるテキスト ---

    def test_full_width_space_text_behavior(self, checker: MojibakeChecker) -> None:
        """境界値: 全角スペース（U+3000）を含むテキストは ftfy に正規化されるため検出対象となる。

        ftfy.fix_text は全角スペース（\u3000）を半角スペースに正規化する。
        このため has_mojibake が True を返し、MojibakeChecker で検出される。
        これは ftfy の Unicode 正規化の仕様による動作である（CJK mojibake として既知）。
        """
        full_width_space_text = "\u3000test content with full-width space"
        dataset = self._make_dataset([full_width_space_text])
        result = checker.check(dataset, text_field="text")

        # ftfy は全角スペースを正規化するため、mojibake として検出される
        # NOTE: docs/design.md「CJK mojibake」の既知制約事項
        assert result.stats["mojibake_count"] == 1

    def test_bom_prefixed_text_detected(self, checker: MojibakeChecker) -> None:
        """境界値: BOM（U+FEFF）付きテキストは ftfy により正規化されるため検出される。"""
        bom_text = "\ufeffText with byte order mark at start of content."
        dataset = self._make_dataset([bom_text])
        result = checker.check(dataset, text_field="text")

        # ftfy は BOM を除去するため変化が生じ、mojibake として検出される
        assert result.stats["mojibake_count"] == 1

    # --- None/非文字列のスキップ ---

    def test_none_values_are_skipped(self, checker: MojibakeChecker) -> None:
        """None 値はスキップされ、文字化けとして検出されない。"""
        dataset = self._make_dataset([None, NORMAL_TEXT_1, None])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["mojibake_count"] == 0

    def test_none_values_not_in_flagged_indices(self, checker: MojibakeChecker) -> None:
        """None が含まれても、WARNING の row_indices に None のインデックスは含まれない。"""
        # index 0: None, index 1: 文字化け, index 2: None
        dataset = self._make_dataset([None, MOJIBAKE_TEXT, None])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        all_flagged_indices = [idx for issue in warnings for idx in issue.row_indices]
        assert 0 not in all_flagged_indices, "None（index 0）は row_indices に含まれないべき"
        assert 2 not in all_flagged_indices, "None（index 2）は row_indices に含まれないべき"
        assert 1 in all_flagged_indices, "文字化けレコード（index 1）は row_indices に含まれるべき"

    def test_none_mixed_with_mojibake_mojibake_count(
        self, checker: MojibakeChecker
    ) -> None:
        """None と文字化けテキスト混在時の mojibake_count が文字化けのみを計上する。"""
        dataset = self._make_dataset([None, MOJIBAKE_TEXT, None, MOJIBAKE_ACCENTED])
        result = checker.check(dataset, text_field="text")

        assert result.stats["mojibake_count"] == 2

    # --- 空データセット ---

    def test_empty_dataset_no_issues(self, checker: MojibakeChecker) -> None:
        """空の Dataset では issues が空リストである。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_empty_dataset_stats(self, checker: MojibakeChecker) -> None:
        """空の Dataset では stats の total_rows, mojibake_count が 0 である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats["total_rows"] == 0
        assert result.stats["mojibake_count"] == 0

    # --- 例外スキップ ---

    def test_exception_in_has_mojibake_is_skipped(
        self, checker: MojibakeChecker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """has_mojibake 呼び出しで例外発生時はそのレコードがスキップされ、issues が空になる。"""
        def _raise(*args, **kwargs):
            raise RuntimeError("ftfy error")

        monkeypatch.setattr("evaldataset.checks.text_quality.has_mojibake", _raise)

        dataset = self._make_dataset([NORMAL_TEXT_1, NORMAL_TEXT_2])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["mojibake_count"] == 0

    # --- メタデータ ---

    def test_checker_name_attribute(self, checker: MojibakeChecker) -> None:
        """name 属性が 'mojibake' であること。"""
        assert checker.name == "mojibake"

    def test_checker_name_in_result(self, checker: MojibakeChecker) -> None:
        """CheckResult.checker_name が 'mojibake' であること。"""
        dataset = self._make_dataset([NORMAL_TEXT_1])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "mojibake"

    def test_issue_checker_field_matches_checker_name(
        self, checker: MojibakeChecker
    ) -> None:
        """Issue.checker フィールドが CheckResult.checker_name と一致すること。"""
        dataset = self._make_dataset([MOJIBAKE_TEXT])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == result.checker_name

    # --- レジストリ登録 ---

    def test_registered_in_registry(self) -> None:
        """MojibakeChecker がレジストリに 'mojibake' として登録されていること。"""
        from evaldataset.checks.registry import get_checker

        cls = get_checker("mojibake")
        assert cls is MojibakeChecker

    # --- 単一レコードのエッジケース ---

    def test_single_row_mojibake_detected(self, checker: MojibakeChecker) -> None:
        """1件だけのデータセットで文字化けが正しく検出される。"""
        dataset = self._make_dataset([MOJIBAKE_ACCENTED])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        assert result.stats["mojibake_count"] == 1
        assert 0 in self._get_warning_indices(result)

    def test_single_row_clean_no_issues(self, checker: MojibakeChecker) -> None:
        """1件だけのデータセットで正常テキストが問題なしと判定される。"""
        dataset = self._make_dataset(["A perfectly clean single row text."])
        result = checker.check(dataset, text_field="text")

        assert not result.has_issues
        assert result.stats["mojibake_count"] == 0
