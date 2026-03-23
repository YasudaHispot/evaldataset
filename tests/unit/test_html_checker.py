"""Unit tests for HTMLChecker.

Covers:
- AC-05-01: HTMLタグ混入の検出（5件以上のタグでWARNING）
- AC-05-02: タグなしテキストでの無検出
- AC-05-03: ソースコードの比較演算子・JSDoc型注釈を誤検出しない
- 境界値: ちょうど5タグで検出
- 境界値: ちょうど4タグで無検出
- 複数レコード混在
- 空データセット
- None値スキップ
- checker_name および severity の検証
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.text_quality import HTMLChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestHTMLChecker:
    """HTMLChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """デフォルト設定の CheckerConfig。"""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> HTMLChecker:
        """HTMLChecker インスタンス。"""
        return HTMLChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。None を含む場合も対応。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-05-01: HTMLタグ混入の検出 ---

    def test_html_tags_5_or_more_triggers_warning(self, checker: HTMLChecker) -> None:
        """AC-05-01: 5件以上のHTMLタグを含むテキストでWARNINGが発生する。

        <p>text</p><div><span>hello</span></div> は合計5タグ:
          <p>, </p>, <div>, <span>, </span>, </div> — 6タグ
        """
        # <p>, </p>, <div>, <span>, </span>, </div> = 6タグ
        html_text = "<p>text</p><div><span>hello</span></div>"
        dataset = self._make_dataset([html_text])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1, "5件以上のHTMLタグがあればWARNINGが発生するべき"

    def test_html_tags_5_or_more_includes_row_index(self, checker: HTMLChecker) -> None:
        """AC-05-01: 検出された Issue の row_indices に対象レコードのインデックスが含まれる。"""
        plain_text = "This is plain text without any tags at all."
        html_text = "<p>text</p><div><span>hello</span></div>"  # 6タグ
        # index 0: plain, index 1: HTML
        dataset = self._make_dataset([plain_text, html_text])
        result = checker.check(dataset, text_field="text")

        warning_indices = [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ]
        assert 1 in warning_indices, "HTMLタグが多いレコード（index 1）がrow_indicesに含まれるべき"
        assert 0 not in warning_indices, "プレーンテキスト（index 0）はrow_indicesに含まれないべき"

    def test_html_detected_count_stat(self, checker: HTMLChecker) -> None:
        """AC-05-01: stats['html_detected_count'] が検出件数と一致する。"""
        html_text_1 = "<p>text</p><div><span>hello</span></div>"  # 6タグ
        html_text_2 = "<h1>Title</h1><p>Para</p><br><ul><li>item</li></ul>"  # 7タグ
        plain_text = "No tags here at all."
        dataset = self._make_dataset([html_text_1, plain_text, html_text_2])
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 2

    def test_severity_is_warning(self, checker: HTMLChecker) -> None:
        """AC-05-01: 検出されたIssueのseverityがWARNINGである。"""
        html_text = "<p>text</p><div><span>hello</span></div>"  # 6タグ
        dataset = self._make_dataset([html_text])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "HTMLタグ多数でIssueが発生するべき"
        for issue in result.issues:
            assert issue.severity == Severity.WARNING, (
                f"Issue の severity は WARNING であるべき: {issue.severity}"
            )

    def test_checker_name_is_html(self, checker: HTMLChecker) -> None:
        """checker_name が 'html' であること。"""
        dataset = self._make_dataset(["plain text"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "html"

    def test_issue_checker_field_matches_checker_name(
        self, checker: HTMLChecker
    ) -> None:
        """Issue.checker フィールドが CheckResult.checker_name と一致すること。"""
        html_text = "<p>text</p><div><span>hello</span></div>"  # 6タグ
        dataset = self._make_dataset([html_text])
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == result.checker_name

    # --- AC-05-02: タグなしテキストでの無検出 ---

    def test_plain_text_no_issues(self, checker: HTMLChecker) -> None:
        """AC-05-02: HTMLタグを含まないプレーンテキストではissuesが空である。"""
        plain_texts = [
            "This is a simple plain text without any HTML.",
            "Another paragraph of pure text content here.",
            "Numbers and symbols: 1234, $100, 50% off!",
        ]
        dataset = self._make_dataset(plain_texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "HTMLタグを含まないテキストでIssueは発生しないべき"

    def test_plain_text_html_detected_count_is_zero(
        self, checker: HTMLChecker
    ) -> None:
        """AC-05-02: プレーンテキストのみの場合 html_detected_count が 0 である。"""
        plain_texts = ["No tags here.", "Still no tags."]
        dataset = self._make_dataset(plain_texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 0

    # --- 境界値: ちょうど5タグで検出 ---

    def test_boundary_exactly_5_tags_triggers_warning(
        self, checker: HTMLChecker
    ) -> None:
        """境界値: ちょうど5つのHTMLタグでWARNINGが発生する。

        <p>, </p>, <b>, <i>, </i> = 5タグ (</b>を省略して5タグに調整)
        実際には <p>text</p><b><i>bold</i></b> = <p>,</p>,<b>,<i>,</i>,</b> = 6タグ
        5タグちょうど: <p>text</p><b>bold</b><i>x</i> = <p>,</p>,<b>,</b>,<i>,</i> = 6タグ
        5タグちょうど: <p>a</p><b>b</b><br><hr><img> = 5タグ (self-closing tags)
        """
        # <p>, </p>, <b>, </b>, <br> = 5タグ
        text_with_5_tags = "<p>text</p><b>bold</b><br>"
        dataset = self._make_dataset([text_with_5_tags])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1, "5タグちょうどでWARNINGが発生するべき"

    def test_boundary_exactly_5_tags_html_detected_count(
        self, checker: HTMLChecker
    ) -> None:
        """境界値: ちょうど5タグで html_detected_count が 1 である。"""
        # <p>, </p>, <b>, </b>, <br> = 5タグ
        text_with_5_tags = "<p>text</p><b>bold</b><br>"
        dataset = self._make_dataset([text_with_5_tags])
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 1

    # --- 境界値: ちょうど4タグで無検出 ---

    def test_boundary_exactly_4_tags_no_warning(self, checker: HTMLChecker) -> None:
        """境界値: ちょうど4つのHTMLタグではWARNINGが発生しない。"""
        # <p>, </p>, <b>, </b> = 4タグ
        text_with_4_tags = "<p>text</p><b>bold</b>"
        dataset = self._make_dataset([text_with_4_tags])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 0, "4タグではWARNINGが発生しないべき"

    def test_boundary_exactly_4_tags_html_detected_count_is_zero(
        self, checker: HTMLChecker
    ) -> None:
        """境界値: ちょうど4タグで html_detected_count が 0 である。"""
        # <p>, </p>, <b>, </b> = 4タグ
        text_with_4_tags = "<p>text</p><b>bold</b>"
        dataset = self._make_dataset([text_with_4_tags])
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 0

    def test_fewer_than_5_tags_no_detection(self, checker: HTMLChecker) -> None:
        """3タグ以下のテキストではWARNINGが発生しない。"""
        # <p>, </p>, <br> = 3タグ
        text_with_3_tags = "<p>text</p><br>"
        dataset = self._make_dataset([text_with_3_tags])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "3タグではIssueが発生しないべき"

    # --- 複数レコード混在 ---

    def test_mixed_records_only_html_detected(self, checker: HTMLChecker) -> None:
        """複数レコード混在: HTMLタグ5件以上のレコードのみ検出される。"""
        texts = [
            "Plain text without HTML tags.",           # index 0: タグなし
            "<p>text</p><div><span>hi</span></div>",  # index 1: 6タグ、検出対象
            "<p>Hello</p><b>World</b>",               # index 2: 4タグ、検出対象外
            "<h1>T</h1><p>A</p><br><ul><li>i</li></ul>",  # index 3: 7タグ、検出対象
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warning_indices = [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ]
        assert 1 in warning_indices, "6タグのレコード（index 1）が検出されるべき"
        assert 3 in warning_indices, "7タグのレコード（index 3）が検出されるべき"
        assert 0 not in warning_indices, "タグなし（index 0）は検出されないべき"
        assert 2 not in warning_indices, "4タグ（index 2）は検出されないべき"

    def test_mixed_records_html_detected_count(self, checker: HTMLChecker) -> None:
        """複数レコード混在: html_detected_count が検出件数と正確に一致する。"""
        texts = [
            "Plain text.",                             # index 0: タグなし
            "<p>t</p><div><span>h</span></div>",      # index 1: 6タグ、検出
            "<p>Hello</p><b>World</b>",               # index 2: 4タグ、非検出
            "<h1>T</h1><p>A</p><br><ul><li>i</li></ul>",  # index 3: 7タグ、検出
            "More plain text here.",                   # index 4: タグなし
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 2

    # --- 空データセット ---

    def test_empty_dataset(self, checker: HTMLChecker) -> None:
        """空の Dataset では issues が空であること。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == []

    def test_empty_dataset_html_detected_count_is_zero(
        self, checker: HTMLChecker
    ) -> None:
        """空の Dataset では html_detected_count が 0 である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("html_detected_count", 0) == 0

    # --- None値スキップ ---

    def test_none_values_are_skipped(self, checker: HTMLChecker) -> None:
        """None値のレコードはスキップされ、検出に影響しない。"""
        dataset = Dataset.from_dict({"text": [None, "plain text", None]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == []
        assert result.stats["html_detected_count"] == 0

    def test_none_mixed_with_html_text(self, checker: HTMLChecker) -> None:
        """None値とHTMLタグ多数のテキストが混在する場合、HTMLのみ検出される。"""
        dataset = Dataset.from_dict(
            {
                "text": [
                    None,                                         # index 0: None、スキップ
                    "<p>t</p><div><span>h</span></div>",         # index 1: 6タグ、検出
                    None,                                         # index 2: None、スキップ
                ]
            }
        )
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 1
        warning_indices = [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ]
        assert 1 in warning_indices
        assert 0 not in warning_indices
        assert 2 not in warning_indices

    # --- エッジケース ---

    def test_text_with_only_lt_gt_symbols_not_detected(
        self, checker: HTMLChecker
    ) -> None:
        """比較演算子の < > をHTMLタグと誤検出しないことを確認するケース。

        NOTE: 正規表現 <[^>]+> はスペースなしのa<bのようなケースはマッチしない。
        a < b のように空白があれば '<' の後に '>' までスペースが含まれないため
        '<[^>]+>' にはマッチしない。
        ただしタグ状の文字列（例: '<br>'）はマッチする。
        """
        # 比較式のように見える記号（HTMLタグではない）
        text = "if a < b and c > d then x < 10"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        # '<[^>]+>' パターンには a<b のような形式のみマッチする（スペースがあればマッチしない）
        # このテストはパターン動作の確認用
        assert result.stats["html_detected_count"] == 0

    def test_large_html_document_detected(self, checker: HTMLChecker) -> None:
        """多数のHTMLタグを含む大きな文書が確実に検出される。"""
        large_html = (
            "<html><head><title>Test</title></head>"
            "<body><h1>Header</h1><p>Paragraph</p>"
            "<div><ul><li>item1</li><li>item2</li></ul></div>"
            "</body></html>"
        )
        dataset = self._make_dataset([large_html])
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
        assert result.stats["html_detected_count"] == 1

    def test_single_record_with_many_html_tags(self, checker: HTMLChecker) -> None:
        """単一レコードで5件以上のタグが検出される典型例。

        <p>text</p><div><span>hello</span></div> の内訳:
        <p>, </p>, <div>, <span>, </span>, </div> = 6タグ
        """
        html_text = "<p>text</p><div><span>hello</span></div>"
        dataset = self._make_dataset([html_text])
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 1
        assert 0 in [
            idx
            for issue in result.issues
            if issue.severity == Severity.WARNING
            for idx in issue.row_indices
        ], "唯一のレコード（index 0）がrow_indicesに含まれるべき"

    def test_all_plain_texts_html_detected_count_is_zero(
        self, checker: HTMLChecker
    ) -> None:
        """全レコードがプレーンテキストの場合、html_detected_count が 0 である。"""
        plain_texts = [
            "First paragraph with no tags.",
            "Second paragraph also tag-free.",
            "Third one too. Numbers: 42, 100%.",
            "Last paragraph without any HTML.",
        ]
        dataset = self._make_dataset(plain_texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["html_detected_count"] == 0
        assert result.issues == []

    # --- AC-05-03: 比較演算子・JSDoc型注釈を誤検出しない ---

    def test_comparison_operators_only_no_issues(self, checker: HTMLChecker) -> None:
        """AC-05-03: 比較演算子（< <= > >=）のみを含むソースコードでissuesが空である。"""
        text = "if (x < 10 && y > 0)"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            f"比較演算子のみのテキストでIssueが発生してはならない: {result.issues}"
        )
        assert result.stats["html_detected_count"] == 0

    def test_jsdoc_type_annotation_no_issues(self, checker: HTMLChecker) -> None:
        """AC-05-03: JSDoc型注釈（@return {Array.<*>}）でissuesが空である。"""
        text = "@return {Array.<*>}"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            f"JSDoc型注釈でIssueが発生してはならない: {result.issues}"
        )
        assert result.stats["html_detected_count"] == 0

    def test_jsdoc_array_of_number_no_issues(self, checker: HTMLChecker) -> None:
        """AC-05-03: JSDoc型注釈（Array.<number>）でissuesが空である。"""
        text = "@param {Array.<number>} arr The input array"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            f"JSDoc Array.<number> 注釈でIssueが発生してはならない: {result.issues}"
        )
        assert result.stats["html_detected_count"] == 0

    def test_multiple_comparison_operators_multiline_no_issues(
        self, checker: HTMLChecker
    ) -> None:
        """AC-05-03: 多数の比較演算子を含む複数行ソースコードでissuesが空である。

        if (a < b) { } if (c > d) { } if (e <= f) { } を複数行繰り返した場合も
        HTMLタグとして誤検出されないことを確認する。
        """
        single_line = "if (a < b) { } if (c > d) { } if (e <= f) { }"
        # 複数行に増やして閾値（5件）を超えうる状況にする
        text = "\n".join([single_line] * 5)
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            f"比較演算子の多行ソースコードでIssueが発生してはならない: {result.issues}"
        )
        assert result.stats["html_detected_count"] == 0

    def test_mixed_html_and_comparison_only_html_counted(
        self, checker: HTMLChecker
    ) -> None:
        """AC-05-03: HTMLタグと比較演算子が混在する場合、HTMLタグのみカウントされる。

        '<p>Hello</p> if (x < 10)' は <p> と </p> の2タグのみカウントされ、
        閾値5未満のためWARNINGは発生しない。
        """
        text = "<p>Hello</p> if (x < 10)"
        dataset = self._make_dataset([text])
        result = checker.check(dataset, text_field="text")

        # <p> と </p> の2タグのみ（閾値5未満）
        assert result.issues == [], (
            "HTMLタグ2件（閾値5未満）ではWARNINGが発生してはならない"
        )
        assert result.stats["html_detected_count"] == 0

    def test_source_code_with_various_comparison_operators_no_issues(
        self, checker: HTMLChecker
    ) -> None:
        """AC-05-03: JavaScript/Pythonソースコードの各種比較演算子で誤検出しない。"""
        source_code = (
            "function compare(a, b) {\n"
            "    if (a < b) return -1;\n"
            "    if (a > b) return 1;\n"
            "    if (a <= b && b >= a) return 0;\n"
            "    return null;\n"
            "}"
        )
        dataset = self._make_dataset([source_code])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], (
            f"JavaScript比較演算子のみのコードでIssueが発生してはならない: {result.issues}"
        )
        assert result.stats["html_detected_count"] == 0
