"""Unit tests for TextCleaner.

Covers:
- AC-12-01: HTMLタグの除去（<p>Hello <b>world</b></p> → "Hello world"）
- AC-12-02: 制御文字の除去（\x00, \x08 除去、\t \n は保持）
- AC-12-03: mojibake の修正（ftfy.fix_text の出力と一致）
- AC-12-04: Dataset 全体修正（複数レコード、修正件数統計）
- 過剰空白の正規化
- パイプライン順序（mojibake → HTML → 制御文字 → 空白）
- 正常テキストは変化なし
- エッジケース: 空文字列、None値の扱い
"""

from __future__ import annotations

import pytest
from datasets import Dataset
from unittest.mock import patch


# --- テストテキスト定数 ---

# HTMLタグを含むテキスト（AC-12-01）
HTML_TEXT_SIMPLE = "<p>Hello <b>world</b></p>"
HTML_TEXT_EXPECTED = "Hello world"

HTML_TEXT_SCRIPT = "<p>Content</p><script>alert('xss')</script><p>More</p>"
HTML_TEXT_STYLE = "<p>Text</p><style>.body { color: red; }</style><p>End</p>"

# 制御文字を含むテキスト（AC-12-02）
TEXT_WITH_NULL = "Hello\x00World"           # \x00 は除去対象
TEXT_WITH_BACKSPACE = "Hello\x08World"      # \x08 は除去対象
TEXT_WITH_TAB = "Hello\tWorld"              # \t は保持
TEXT_WITH_NEWLINE = "Hello\nWorld"          # \n は保持
TEXT_WITH_CARRIAGE_RETURN = "Hello\rWorld"  # \r は保持

# mojibake テキスト（AC-12-03）
# UTF-8をWindows-1252として誤解釈したパターン: "hello" → \xe2\x80\x9chello\xe2\x80\x9d
MOJIBAKE_TEXT = "\u00e2\u0080\u009chello\u00e2\u0080\u009d"

# 正常テキスト
NORMAL_TEXT = "This is a perfectly clean text without any issues."
NORMAL_TEXT_2 = "Another clean paragraph with proper UTF-8 encoding."

# 過剰空白を含むテキスト
TEXT_EXCESSIVE_SPACES = "Hello    World"    # スペース4つ → 正規化
TEXT_EXCESSIVE_NEWLINES = "Hello\n\n\n\nWorld"  # 改行4つ → 正規化


class TestTextCleanerFixText:
    """TextCleaner.fix_text のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def cleaner(self):
        """TextCleaner インスタンス。"""
        from evaldataset.fixer import TextCleaner
        return TextCleaner()

    # --- AC-12-01: HTMLタグの除去 ---

    def test_html_tags_removed_simple(self, cleaner) -> None:
        """AC-12-01: <p>Hello <b>world</b></p> → 'Hello world' になる。"""
        result = cleaner.fix_text(HTML_TEXT_SIMPLE)
        assert result == HTML_TEXT_EXPECTED

    def test_html_tags_removed_nested(self, cleaner) -> None:
        """AC-12-01: ネストされたHTMLタグが全て除去される。"""
        html = "<div><h1>Title</h1><p>Paragraph <span>text</span></p></div>"
        result = cleaner.fix_text(html)
        assert "<" not in result
        assert ">" not in result
        assert "Title" in result
        assert "Paragraph" in result
        assert "text" in result

    def test_html_script_tag_content_removed(self, cleaner) -> None:
        """AC-12-01: <script>タグとその内容が除去される。"""
        result = cleaner.fix_text(HTML_TEXT_SCRIPT)
        assert "alert" not in result
        assert "Content" in result
        assert "More" in result

    def test_html_style_tag_content_removed(self, cleaner) -> None:
        """AC-12-01: <style>タグとその内容が除去される。"""
        result = cleaner.fix_text(HTML_TEXT_STYLE)
        assert "color" not in result
        assert "Text" in result
        assert "End" in result

    def test_html_result_has_no_tags(self, cleaner) -> None:
        """AC-12-01: 修正後のテキストにHTMLタグが含まれない。"""
        complex_html = (
            "<html><head><title>Doc</title></head>"
            "<body><h1>Header</h1><p>Body text</p></body></html>"
        )
        result = cleaner.fix_text(complex_html)
        assert "<" not in result
        assert ">" not in result

    # --- AC-12-02: 制御文字の除去 ---

    def test_null_character_removed(self, cleaner) -> None:
        """AC-12-02: \\x00（NULL文字）が除去される。"""
        result = cleaner.fix_text(TEXT_WITH_NULL)
        assert "\x00" not in result
        assert "Hello" in result
        assert "World" in result

    def test_backspace_character_removed(self, cleaner) -> None:
        """AC-12-02: \\x08（バックスペース）が除去される。"""
        result = cleaner.fix_text(TEXT_WITH_BACKSPACE)
        assert "\x08" not in result
        assert "Hello" in result
        assert "World" in result

    def test_tab_preserved(self, cleaner) -> None:
        """AC-12-02: \\t（タブ）は保持される。"""
        result = cleaner.fix_text(TEXT_WITH_TAB)
        assert "\t" in result

    def test_newline_preserved(self, cleaner) -> None:
        """AC-12-02: \\n（改行）は保持される。"""
        result = cleaner.fix_text(TEXT_WITH_NEWLINE)
        assert "\n" in result

    def test_carriage_return_converted_by_ftfy(self, cleaner) -> None:
        """AC-12-02: \\r（キャリッジリターン）は制御文字除去ステップでは保持される。

        ただし、パイプライン最初の ftfy.fix_text が \\r を \\n に正規化するため、
        fix_text() 全体としては \\r は \\n に変換される。
        これは ftfy の Unicode 正規化の既知の動作（\\r は改行として扱われる）。
        """
        result = cleaner.fix_text(TEXT_WITH_CARRIAGE_RETURN)
        # ftfy により \r は \n に変換されるため、改行文字として保持される
        assert "\n" in result or "\r" in result

    def test_multiple_control_chars_removed(self, cleaner) -> None:
        """AC-12-02: 複数の制御文字が全て除去される。"""
        text_with_multiple_controls = "A\x00B\x08C\x01D\x02E"
        result = cleaner.fix_text(text_with_multiple_controls)
        assert "\x00" not in result
        assert "\x08" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "ABCDE" in result

    def test_tab_and_newline_preserved_alongside_control_removal(
        self, cleaner
    ) -> None:
        """AC-12-02: \t \n を保持しつつ \x00 等の制御文字を除去する。"""
        mixed_text = "Hello\t\x00World\nDone\x08End"
        result = cleaner.fix_text(mixed_text)
        assert "\t" in result
        assert "\n" in result
        assert "\x00" not in result
        assert "\x08" not in result

    # --- AC-12-03: mojibake の修正 ---

    def test_mojibake_fixed_matches_ftfy_output(self, cleaner) -> None:
        """AC-12-03: mojibake 修正後の出力が ftfy.fix_text の出力と一致する。"""
        import ftfy
        expected = ftfy.fix_text(MOJIBAKE_TEXT)
        result = cleaner.fix_text(MOJIBAKE_TEXT)
        assert result == expected

    def test_mojibake_accented_chars_fixed(self, cleaner) -> None:
        """AC-12-03: アクセント文字の文字化けが修正される。"""
        import ftfy
        # é が Ã© として化けたテキスト
        mojibake_accented = "\u00c3\u00a9"
        expected = ftfy.fix_text(mojibake_accented)
        result = cleaner.fix_text(mojibake_accented)
        assert result == expected

    def test_mojibake_alt_quotes_fixed(self, cleaner) -> None:
        """AC-12-03: 代替引用符の文字化けが修正される。"""
        import ftfy
        mojibake_quotes = "\u00e2\u20ac\u009chello\u00e2\u20ac\u009d"
        expected = ftfy.fix_text(mojibake_quotes)
        result = cleaner.fix_text(mojibake_quotes)
        assert result == expected

    # --- 過剰空白の正規化 ---

    def test_excessive_spaces_normalized(self, cleaner) -> None:
        """過剰な連続空白が正規化される（3つ以上の連続スペースが短縮される）。"""
        result = cleaner.fix_text(TEXT_EXCESSIVE_SPACES)
        # 3つ以上の連続スペースがなくなること
        assert "    " not in result
        assert "Hello" in result
        assert "World" in result

    def test_excessive_newlines_normalized(self, cleaner) -> None:
        """過剰な連続改行が正規化される（4つ以上の連続改行が短縮される）。"""
        result = cleaner.fix_text(TEXT_EXCESSIVE_NEWLINES)
        # 4つ以上の連続改行がなくなること
        assert "\n\n\n\n" not in result
        assert "Hello" in result
        assert "World" in result

    def test_leading_trailing_whitespace_stripped(self, cleaner) -> None:
        """先頭・末尾の空白が除去される。"""
        text_with_padding = "   Hello World   "
        result = cleaner.fix_text(text_with_padding)
        assert result == result.strip()
        assert "Hello World" in result

    # --- パイプライン順序（mojibake → HTML → 制御文字 → 空白）---

    def test_pipeline_mojibake_then_html(self, cleaner) -> None:
        """パイプライン: mojibake修正後にHTMLタグ除去が適用される。

        mojibake修正→HTML除去の順序が正しく機能することを確認する。
        """
        # 正常なHTML（mojibake修正後にHTML除去が走る）
        html_text = "<p>Hello world</p>"
        result = cleaner.fix_text(html_text)
        assert "<p>" not in result
        assert "Hello world" in result

    def test_pipeline_html_then_control_chars(self, cleaner) -> None:
        """パイプライン: HTML除去後に制御文字除去が適用される。

        HTML除去→制御文字除去の順序で結果が正しいことを確認する。
        """
        html_with_control = "<p>Hello\x00World</p>"
        result = cleaner.fix_text(html_with_control)
        assert "<p>" not in result
        assert "\x00" not in result
        assert "Hello" in result
        assert "World" in result

    def test_pipeline_all_steps_applied(self, cleaner) -> None:
        """パイプライン: 全ステップ（mojibake→HTML→制御文字→空白）が適用される。"""
        # 全問題を含むテキスト
        complex_text = "<p>Hello\x00World   </p>"
        result = cleaner.fix_text(complex_text)
        # HTMLタグが除去されている
        assert "<p>" not in result
        assert "</p>" not in result
        # NULL文字が除去されている
        assert "\x00" not in result
        # コンテンツが保持されている
        assert "Hello" in result
        assert "World" in result

    # --- 正常テキストは変化なし ---

    def test_normal_text_unchanged(self, cleaner) -> None:
        """正常テキストは fix_text 適用後も変化しない。"""
        result = cleaner.fix_text(NORMAL_TEXT)
        assert result == NORMAL_TEXT

    def test_normal_text_with_tabs_unchanged(self, cleaner) -> None:
        """タブと改行を含む正常テキストは fix_text 適用後に \t \n が保持される。"""
        normal_with_whitespace = "Line one\n\tIndented line\nLine three"
        result = cleaner.fix_text(normal_with_whitespace)
        assert "\n" in result
        assert "\t" in result
        assert "Line one" in result
        assert "Indented line" in result

    # --- エッジケース: 空文字列 ---

    def test_empty_string_returns_empty_string(self, cleaner) -> None:
        """空文字列を入力すると空文字列が返される。"""
        result = cleaner.fix_text("")
        assert result == ""

    def test_whitespace_only_string(self, cleaner) -> None:
        """空白のみの文字列が適切に処理される（空文字列または空白除去後）。"""
        result = cleaner.fix_text("   ")
        # 空白のみ → strip後は空文字列になることを期待
        assert result.strip() == ""

    def test_single_character_preserved(self, cleaner) -> None:
        """1文字の正常テキストが保持される。"""
        result = cleaner.fix_text("A")
        assert result == "A"


class TestTextCleanerFixDataset:
    """TextCleaner.fix_dataset のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def cleaner(self):
        """TextCleaner インスタンス。"""
        from evaldataset.fixer import TextCleaner
        return TextCleaner()

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-12-04: Dataset 全体修正 ---

    def test_fix_dataset_returns_tuple_of_dataset_and_stats(self, cleaner) -> None:
        """AC-12-04: fix_dataset は (Dataset, dict) のタプルを返す。"""
        dataset = self._make_dataset([HTML_TEXT_SIMPLE, NORMAL_TEXT])
        result = cleaner.fix_dataset(dataset, text_field="text")
        assert isinstance(result, tuple)
        assert len(result) == 2
        result_dataset, stats = result
        assert isinstance(result_dataset, Dataset)
        assert isinstance(stats, dict)

    def test_fix_dataset_html_tags_removed_in_all_records(self, cleaner) -> None:
        """AC-12-04: 複数レコードのHTMLタグが全て除去される。"""
        dataset = self._make_dataset([
            "<p>Hello <b>world</b></p>",
            "<div><span>Another</span> text</div>",
            NORMAL_TEXT,
        ])
        result_dataset, _ = cleaner.fix_dataset(dataset, text_field="text")

        for text in result_dataset["text"]:
            if text is not None:
                assert "<" not in text
                assert ">" not in text

    def test_fix_dataset_control_chars_removed_in_all_records(
        self, cleaner
    ) -> None:
        """AC-12-04: 複数レコードの制御文字が全て除去される。"""
        dataset = self._make_dataset([
            "Hello\x00World",
            "Test\x08End",
            NORMAL_TEXT,
        ])
        result_dataset, _ = cleaner.fix_dataset(dataset, text_field="text")

        for text in result_dataset["text"]:
            if text is not None:
                assert "\x00" not in text
                assert "\x08" not in text

    def test_fix_dataset_clean_records_unchanged(self, cleaner) -> None:
        """AC-12-04: 修正不要なレコードの内容は変化しない。"""
        clean_texts = [NORMAL_TEXT, NORMAL_TEXT_2]
        dataset = self._make_dataset(clean_texts)
        result_dataset, _ = cleaner.fix_dataset(dataset, text_field="text")

        result_texts = result_dataset["text"]
        assert result_texts[0] == NORMAL_TEXT
        assert result_texts[1] == NORMAL_TEXT_2

    def test_fix_dataset_returns_correct_row_count(self, cleaner) -> None:
        """AC-12-04: 修正後のDatasetの行数が元のDatasetと同じである。"""
        texts = [
            "<p>Hello</p>",
            NORMAL_TEXT,
            "Test\x00End",
            NORMAL_TEXT_2,
        ]
        dataset = self._make_dataset(texts)
        result_dataset, _ = cleaner.fix_dataset(dataset, text_field="text")

        assert len(result_dataset) == len(dataset)

    def test_fix_dataset_returns_stats(self, cleaner) -> None:
        """AC-12-04: fix_dataset は修正件数を含むstatsを記録する。"""
        dataset = self._make_dataset([
            "<p>Hello <b>world</b></p>",
            NORMAL_TEXT,
            "Test\x00End",
        ])
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")
        # stats に修正件数が含まれること
        assert isinstance(stats, dict)
        assert "total_fixed" in stats

    def test_fix_dataset_fixed_count_matches_modified_records(
        self, cleaner
    ) -> None:
        """AC-12-04: stats['total_fixed'] が実際に修正されたレコード数と一致する。"""
        dataset = self._make_dataset([
            "<p>Hello <b>world</b></p>",  # 修正対象
            NORMAL_TEXT,                   # 修正不要
            "Test\x00End",                 # 修正対象
            NORMAL_TEXT_2,                 # 修正不要
        ])
        _, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert stats["total_fixed"] == 2

    def test_fix_dataset_fixed_count_zero_when_no_modifications(
        self, cleaner
    ) -> None:
        """AC-12-04: 修正不要なレコードのみの場合 total_fixed が 0 である。"""
        dataset = self._make_dataset([NORMAL_TEXT, NORMAL_TEXT_2])
        _, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert stats["total_fixed"] == 0

    def test_fix_dataset_total_rows_in_stats(self, cleaner) -> None:
        """AC-12-04: stats に total_rows が記録される。"""
        texts = [NORMAL_TEXT, NORMAL_TEXT_2, "<p>Hello</p>"]
        dataset = self._make_dataset(texts)
        _, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert "total_rows" in stats
        assert stats["total_rows"] == 3

    def test_fix_dataset_single_record_with_html(self, cleaner) -> None:
        """AC-12-04: 1件のHTMLテキストが修正される。"""
        dataset = self._make_dataset(["<p>Hello <b>world</b></p>"])
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert "<" not in result_dataset["text"][0]
        assert stats["total_fixed"] == 1

    def test_fix_dataset_preserves_non_text_columns(self, cleaner) -> None:
        """AC-12-04: テキスト以外の列は変更されずに保持される。"""
        dataset = Dataset.from_dict({
            "text": ["<p>Hello</p>", NORMAL_TEXT],
            "id": [1, 2],
            "label": ["A", "B"],
        })
        result_dataset, _ = cleaner.fix_dataset(dataset, text_field="text")

        assert result_dataset["id"] == [1, 2]
        assert result_dataset["label"] == ["A", "B"]

    # --- エッジケース: None値の扱い ---

    def test_fix_dataset_none_values_handled(self, cleaner) -> None:
        """None値を含むDatasetが例外なく処理される。"""
        dataset = self._make_dataset([None, NORMAL_TEXT, None])
        # 例外が発生しないこと
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")
        assert len(result_dataset) == 3

    def test_fix_dataset_none_not_counted_as_fixed(self, cleaner) -> None:
        """None値は修正件数に計上されない。"""
        dataset = self._make_dataset([None, None])
        _, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert stats["total_fixed"] == 0

    def test_fix_dataset_empty_dataset(self, cleaner) -> None:
        """空のDatasetが例外なく処理され、total_fixedが0になる。"""
        dataset = self._make_dataset([])
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert len(result_dataset) == 0
        assert stats["total_fixed"] == 0
        assert stats["total_rows"] == 0

    def test_fix_dataset_all_none_values(self, cleaner) -> None:
        """全レコードがNoneのDatasetが例外なく処理される。"""
        dataset = self._make_dataset([None, None, None])
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert len(result_dataset) == 3
        assert stats["total_fixed"] == 0

    def test_fix_dataset_mixed_none_and_html(self, cleaner) -> None:
        """None値とHTMLテキストが混在するDatasetで正しく修正される。"""
        dataset = self._make_dataset([
            None,                          # None: スキップ
            "<p>Hello <b>world</b></p>",  # HTML: 修正対象
            None,                          # None: スキップ
            NORMAL_TEXT,                   # 正常: 修正不要
        ])
        result_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        assert stats["total_fixed"] == 1
        assert "<" not in result_dataset["text"][1]
        assert result_dataset["text"][0] is None
        assert result_dataset["text"][2] is None


class TestTextCleanerInternalSteps:
    """TextCleaner の個別パイプラインステップのテスト。"""

    @pytest.fixture
    def cleaner(self):
        """TextCleaner インスタンス。"""
        from evaldataset.fixer import TextCleaner
        return TextCleaner()

    def test_remove_control_chars_preserves_tab(self, cleaner) -> None:
        """_remove_control_chars は \\t を保持する。"""
        result = cleaner._remove_control_chars("Hello\tWorld")
        assert "\t" in result

    def test_remove_control_chars_preserves_newline(self, cleaner) -> None:
        """_remove_control_chars は \\n を保持する。"""
        result = cleaner._remove_control_chars("Hello\nWorld")
        assert "\n" in result

    def test_remove_control_chars_preserves_carriage_return(self, cleaner) -> None:
        """_remove_control_chars は \\r を保持する。"""
        result = cleaner._remove_control_chars("Hello\rWorld")
        assert "\r" in result

    def test_remove_control_chars_removes_null(self, cleaner) -> None:
        """_remove_control_chars は \\x00 を除去する。"""
        result = cleaner._remove_control_chars("Hello\x00World")
        assert "\x00" not in result

    def test_strip_html_removes_tags(self, cleaner) -> None:
        """_strip_html はHTMLタグを除去してテキストコンテンツを返す。"""
        result = cleaner._strip_html("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_fix_mojibake_calls_ftfy(self, cleaner) -> None:
        """_fix_mojibake が ftfy.fix_text の出力と一致する。"""
        import ftfy
        mojibake = "\u00e2\u0080\u009chello\u00e2\u0080\u009d"
        result = cleaner._fix_mojibake(mojibake)
        assert result == ftfy.fix_text(mojibake)

    def test_normalize_whitespace_collapses_excessive_spaces(self, cleaner) -> None:
        """_normalize_whitespace は連続する多数のスペースを短縮する。"""
        result = cleaner._normalize_whitespace("Hello    World")
        assert "    " not in result
        assert "Hello" in result
        assert "World" in result

    def test_normalize_whitespace_strips_edges(self, cleaner) -> None:
        """_normalize_whitespace は先頭・末尾の空白を除去する。"""
        result = cleaner._normalize_whitespace("   Hello World   ")
        assert result == result.strip()
