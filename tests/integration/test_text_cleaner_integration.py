"""Integration tests for TextCleaner.

IT: TextCleaner
Source: docs/design.md — TextCleaner 受入条件 (AC-12-01, AC-12-02, AC-12-03, AC-12-04)
"""

from datasets import Dataset

from evaldataset.fixer import TextCleaner


class TestTextCleanerIntegration:
    """
    IT: TextCleaner
    Source: docs/design.md — TextCleaner 受入条件 (AC-12-01, AC-12-02, AC-12-03, AC-12-04)
    """

    def test_fix_text_removes_html_tags(self):
        """
        AC-12-01: HTMLタグの除去

        Given: <p>Hello <b>world</b></p> のようなHTMLタグを含むテキスト
        When: TextCleaner.fix_text(text) を実行する
        Then: 戻り値が "Hello world" のようにHTMLタグを含まないプレーンテキストになる
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        html_text = "<p>Hello <b>world</b></p>"

        # Act (When)
        result = cleaner.fix_text(html_text)

        # Assert (Then)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "</b>" not in result
        assert "</p>" not in result
        assert "Hello" in result
        assert "world" in result

    def test_fix_text_removes_html_tags_complex(self):
        """
        AC-12-01: HTMLタグの除去（複雑なケース）

        Given: 複数のHTMLタグ（div, span, a）を含むテキスト
        When: TextCleaner.fix_text(text) を実行する
        Then: 全てのHTMLタグが除去され、テキスト内容のみが残る
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        html_text = '<div><span class="highlight">Important</span> <a href="http://example.com">link</a></div>'

        # Act (When)
        result = cleaner.fix_text(html_text)

        # Assert (Then)
        assert "<div>" not in result
        assert "<span" not in result
        assert "<a " not in result
        assert "Important" in result
        assert "link" in result

    def test_fix_text_removes_control_characters(self):
        """
        AC-12-02: 制御文字の除去

        Given: \\t と \\n 以外の制御文字（\\x00, \\x08）を含むテキスト
        When: TextCleaner.fix_text(text) を実行する
        Then: 制御文字が除去され、\\t と \\n はそのまま保持される
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        text_with_control_chars = "Hello\x00World\x08Test\tTab\nNewline"

        # Act (When)
        result = cleaner.fix_text(text_with_control_chars)

        # Assert (Then)
        assert "\x00" not in result
        assert "\x08" not in result
        assert "\t" in result
        assert "\n" in result
        assert "Hello" in result
        assert "World" in result
        assert "Test" in result
        assert "Tab" in result
        assert "Newline" in result

    def test_fix_text_preserves_tab_and_newline(self):
        """
        AC-12-02: 制御文字の除去（\\t と \\n の保持確認）

        Given: \\t と \\n のみを含むテキスト（有害な制御文字なし）
        When: TextCleaner.fix_text(text) を実行する
        Then: テキストがそのまま保持される
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        text = "Line1\tTabbed\nLine2"

        # Act (When)
        result = cleaner.fix_text(text)

        # Assert (Then)
        assert "\t" in result
        assert "\n" in result
        assert "Line1" in result
        assert "Tabbed" in result
        assert "Line2" in result

    def test_fix_text_corrects_mojibake(self):
        """
        AC-12-03: mojibake の修正

        Given: ftfy.fix_text で修正可能な文字化けテキスト（例: "â€œhelloâ€\\x9d"）
        When: TextCleaner.fix_text(text) を実行する
        Then: 文字化けが修正される
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        mojibake_text = "\u00e2\u0080\u009chello\u00e2\u0080\u009d"  # mojibake for "hello"

        # Act (When)
        result = cleaner.fix_text(mojibake_text)

        # Assert (Then)
        assert "hello" in result
        # The mojibake should be fixed; the raw byte sequences should not remain
        assert "\u00e2\u0080\u009c" not in result
        assert "\u00e2\u0080\u009d" not in result

    def test_fix_dataset_cleans_all_records(self):
        """
        AC-12-04: Dataset 全体修正

        Given: HTMLタグや制御文字を含む複数レコードの Dataset
        When: TextCleaner.fix_dataset(dataset, text_field="text") を実行する
        Then: 修正済み Dataset が返され、修正件数の統計dictが返される
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        texts = [
            "<p>Hello <b>world</b></p>",
            "Normal text without issues",
            "Text with\x00control\x08chars",
            "\u00e2\u0080\u009cmojibake\u00e2\u0080\u009d",
        ]
        dataset = Dataset.from_dict({"text": texts})

        # Act (When)
        fixed_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        # Assert (Then)
        # fixed_dataset should be a Dataset
        assert isinstance(fixed_dataset, Dataset)
        assert len(fixed_dataset) == len(texts)

        # HTML tags should be removed in first record
        assert "<p>" not in fixed_dataset[0]["text"]
        assert "<b>" not in fixed_dataset[0]["text"]
        assert "Hello" in fixed_dataset[0]["text"]
        assert "world" in fixed_dataset[0]["text"]

        # Normal text should be unchanged
        assert fixed_dataset[1]["text"] == "Normal text without issues"

        # Control characters should be removed in third record
        assert "\x00" not in fixed_dataset[2]["text"]
        assert "\x08" not in fixed_dataset[2]["text"]

        # Mojibake should be fixed in fourth record
        assert "mojibake" in fixed_dataset[3]["text"]

        # stats should be a dict with fix counts
        assert isinstance(stats, dict)

    def test_fix_dataset_returns_stats_with_fix_counts(self):
        """
        AC-12-04: Dataset 全体修正（統計の検証）

        Given: 修正が必要なレコードと不要なレコードが混在する Dataset
        When: TextCleaner.fix_dataset(dataset, text_field="text") を実行する
        Then: 統計dictに修正件数が含まれ、修正が必要だったレコード数が反映される
        """
        # Arrange (Given)
        cleaner = TextCleaner()
        texts = [
            "<p>HTML content</p>",
            "Clean text",
            "Another clean text",
        ]
        dataset = Dataset.from_dict({"text": texts})

        # Act (When)
        fixed_dataset, stats = cleaner.fix_dataset(dataset, text_field="text")

        # Assert (Then)
        assert isinstance(stats, dict)
        # At least one record was fixed (the HTML one), so stats should reflect that
        total_fixed = sum(v for v in stats.values() if isinstance(v, int))
        assert total_fixed >= 1
