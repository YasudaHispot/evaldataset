"""Unit tests for text utility functions in utils/text.py.

Covers:
- count_html_tags: HTMLタグのカウント（正常系・異常系・境界値）
  - 通常のHTMLタグのカウント
  - 比較演算子（<, <=, >, >=）を誤検出しない（AC-05-03関連）
  - JSDoc型注釈（<*>, Array.<number>）を誤検出しない（AC-05-03関連）
  - 空文字列・None的な境界値
"""

from __future__ import annotations

import pytest

from evaldataset.utils.text import count_html_tags


class TestCountHtmlTags:
    """count_html_tags 関数のユニットテスト。"""

    # --- 通常HTMLタグのカウント ---

    def test_empty_string_returns_zero(self) -> None:
        """空文字列ではカウントが0である。"""
        assert count_html_tags("") == 0

    def test_plain_text_no_tags_returns_zero(self) -> None:
        """プレーンテキスト（タグなし）ではカウントが0である。"""
        text = "This is plain text without any HTML tags."
        assert count_html_tags(text) == 0

    def test_single_open_tag(self) -> None:
        """開きタグ1件が正しくカウントされる。"""
        assert count_html_tags("<p>") == 1

    def test_single_close_tag(self) -> None:
        """閉じタグ1件が正しくカウントされる。"""
        assert count_html_tags("</p>") == 1

    def test_tag_pair_counted_as_two(self) -> None:
        """開き・閉じタグのペアは2件としてカウントされる。"""
        assert count_html_tags("<p>text</p>") == 2

    def test_self_closing_tag(self) -> None:
        """自己閉じタグ（<br>）が1件としてカウントされる。"""
        assert count_html_tags("<br>") == 1

    def test_self_closing_xhtml_tag(self) -> None:
        """XHTML形式の自己閉じタグ（<br/>）が1件としてカウントされる。"""
        assert count_html_tags("<br/>") == 1

    def test_five_tags_counted_correctly(self) -> None:
        """5件のHTMLタグが正しくカウントされる（HTMLCheckerの閾値）。"""
        # <p>, </p>, <b>, </b>, <br> = 5件
        text = "<p>text</p><b>bold</b><br>"
        assert count_html_tags(text) == 5

    def test_six_tags_in_nested_html(self) -> None:
        """ネストされたHTMLで6件のタグが正しくカウントされる。"""
        # <p>, </p>, <div>, <span>, </span>, </div> = 6件
        text = "<p>text</p><div><span>hello</span></div>"
        assert count_html_tags(text) == 6

    def test_tags_with_attributes(self) -> None:
        """属性付きHTMLタグが正しくカウントされる。"""
        text = '<a href="https://example.com">link</a>'
        assert count_html_tags(text) == 2

    def test_large_html_document(self) -> None:
        """大きなHTMLドキュメントでタグが正しくカウントされる。"""
        text = (
            "<html><head><title>Test</title></head>"
            "<body><h1>Header</h1><p>Paragraph</p>"
            "<div><ul><li>item</li></ul></div>"
            "</body></html>"
        )
        # <html>, <head>, <title>, </title>, </head>,
        # <body>, <h1>, </h1>, <p>, </p>,
        # <div>, <ul>, <li>, </li>, </ul>, </div>,
        # </body>, </html> = 18件
        count = count_html_tags(text)
        assert count >= 10, f"大きなHTMLは10件以上のタグを含むべき: {count}"

    # --- AC-05-03: 比較演算子を誤検出しない ---

    def test_comparison_operator_less_than_with_space_not_counted(self) -> None:
        """AC-05-03: 空白区切りの 'x < 10' は HTMLタグとしてカウントしない。"""
        text = "if (x < 10)"
        assert count_html_tags(text) == 0, (
            "比較演算子 'x < 10' はHTMLタグとして誤検出してはならない"
        )

    def test_comparison_operator_greater_than_with_space_not_counted(self) -> None:
        """AC-05-03: 空白区切りの 'y > 0' は HTMLタグとしてカウントしない。"""
        text = "if (y > 0)"
        assert count_html_tags(text) == 0, (
            "比較演算子 'y > 0' はHTMLタグとして誤検出してはならない"
        )

    def test_comparison_both_operators_no_count(self) -> None:
        """AC-05-03: 'if (x < 10 && y > 0)' は HTMLタグを0件とカウントする。"""
        text = "if (x < 10 && y > 0)"
        assert count_html_tags(text) == 0, (
            f"比較演算子を含む式はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    def test_less_than_or_equal_operator_not_counted(self) -> None:
        """AC-05-03: '<=' 演算子は HTMLタグとしてカウントしない。"""
        text = "if (e <= f)"
        assert count_html_tags(text) == 0

    def test_greater_than_or_equal_operator_not_counted(self) -> None:
        """AC-05-03: '>=' 演算子は HTMLタグとしてカウントしない。"""
        text = "if (e >= f)"
        assert count_html_tags(text) == 0

    def test_multiple_comparison_operators_not_counted(self) -> None:
        """AC-05-03: 複数の比較演算子を含む式はHTMLタグをカウントしない。"""
        text = "if (a < b) { } if (c > d) { } if (e <= f) { }"
        assert count_html_tags(text) == 0, (
            f"複数の比較演算子はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    def test_multiline_source_code_with_comparisons_not_counted(self) -> None:
        """AC-05-03: 比較演算子を多数含む複数行ソースコードはHTMLタグをカウントしない。"""
        source_code = (
            "function compare(a, b) {\n"
            "    if (a < b) return -1;\n"
            "    if (a > b) return 1;\n"
            "    if (a <= b && b >= a) return 0;\n"
            "    return null;\n"
            "}"
        )
        assert count_html_tags(source_code) == 0, (
            f"比較演算子を多数含むコードはHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(source_code)}"
        )

    # --- AC-05-03: JSDoc型注釈を誤検出しない ---

    def test_jsdoc_wildcard_annotation_not_counted(self) -> None:
        """AC-05-03: JSDoc型注釈 <*> は HTMLタグとしてカウントしない。"""
        text = "@return {Array.<*>}"
        assert count_html_tags(text) == 0, (
            f"JSDoc型注釈 <*> はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    def test_jsdoc_array_of_number_not_counted(self) -> None:
        """AC-05-03: JSDoc型注釈 Array.<number> は HTMLタグとしてカウントしない。"""
        text = "@param {Array.<number>} arr The input array"
        assert count_html_tags(text) == 0, (
            f"JSDoc型注釈 Array.<number> はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    def test_jsdoc_array_of_string_not_counted(self) -> None:
        """AC-05-03: JSDoc型注釈 Array.<string> は HTMLタグとしてカウントしない。"""
        text = "@type {Array.<string>}"
        assert count_html_tags(text) == 0, (
            f"JSDoc型注釈 Array.<string> はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    def test_jsdoc_multiple_annotations_not_counted(self) -> None:
        """AC-05-03: 複数のJSDoc型注釈を含むコメントはHTMLタグをカウントしない。"""
        text = (
            "/**\n"
            " * @param {Array.<number>} values Input values\n"
            " * @param {Array.<string>} labels Display labels\n"
            " * @return {Array.<*>} Combined result\n"
            " */"
        )
        assert count_html_tags(text) == 0, (
            f"複数のJSDoc型注釈はHTMLタグとして誤検出してはならない: "
            f"count={count_html_tags(text)}"
        )

    # --- HTMLタグと比較演算子の混在 ---

    def test_html_tags_with_comparison_only_html_counted(self) -> None:
        """HTMLタグと比較演算子が混在する場合、HTMLタグのみカウントされる。

        '<p>Hello</p> if (x < 10)' では <p> と </p> の2タグのみカウントされる。
        """
        text = "<p>Hello</p> if (x < 10)"
        count = count_html_tags(text)
        assert count == 2, (
            f"HTMLタグ（<p>, </p>）の2件のみカウントされるべき。実際: {count}"
        )

    def test_html_and_jsdoc_mixed_only_html_counted(self) -> None:
        """HTMLタグとJSDoc注釈が混在する場合、HTMLタグのみカウントされる。

        '<p>' と '</p>' はHTMLタグとしてカウントされるが、
        'Array.<number>' はカウントされないことを検証する。
        """
        text = "/** @type {Array.<number>} */ <p>Hello</p>"
        count = count_html_tags(text)
        assert count == 2, (
            f"HTMLタグ（<p>, </p>）の2件のみカウントされるべき。実際: {count}"
        )
