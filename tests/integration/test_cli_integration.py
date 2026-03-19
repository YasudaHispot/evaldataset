"""Integration tests for evaldataset CLI.

IT: evaldataset CLI
Source: docs/design.md — CLI受入条件 (AC-14-01, AC-14-01b, AC-14-02, AC-14-03,
        AC-14-03b, AC-14-04, AC-14-05, AC-14-06) および
        レポート受入条件 (AC-13-02, AC-13-03)
"""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner
from datasets import Dataset
from unittest.mock import patch

from evaldataset.cli import main


# ---------------------------------------------------------------------------
# テスト用データセットファクトリ
# ---------------------------------------------------------------------------

def _clean_dataset(n: int = 5) -> Dataset:
    """品質問題がない正常なデータセット（n件）を返す。

    各テキストはユニークな内容にし、near-duplicate WARNING を回避する。
    """
    unique_contents = [
        "The quick brown fox jumps over the lazy dog with agility and grace.",
        "Machine learning algorithms process large amounts of data efficiently.",
        "Natural language processing enables computers to understand human speech.",
        "Data science combines statistics, mathematics, and programming effectively.",
        "Cloud computing provides scalable infrastructure for modern applications.",
        "Artificial intelligence transforms industries and reshapes human work patterns.",
        "Software engineering requires careful design, testing, and documentation practices.",
        "Database systems store and retrieve structured information with reliability.",
        "Network security protects digital assets from unauthorized access and threats.",
        "Web development creates interactive applications using modern browser technologies.",
    ]
    texts = [unique_contents[i % len(unique_contents)] + f" Document {i}."
             for i in range(n)]
    return Dataset.from_dict({"text": texts})


def _dataset_with_warnings() -> Dataset:
    """WARNING レベルの Issue（短すぎるテキスト）を含むデータセットを返す。"""
    return Dataset.from_dict({
        "text": [
            "Short",  # 50文字未満 → TextLengthChecker が WARNING を発生させる
            "This is a normal document with sufficient text length for quality checks.",
        ]
    })


def _dataset_with_errors() -> Dataset:
    """ERROR レベルの Issue（Noneフィールド）を含むデータセットを返す。"""
    return Dataset.from_dict({
        "text": [None, "Normal text with sufficient length for quality checks."]
    })


def _large_dataset(n: int = 200) -> Dataset:
    """1,000件未満だが --sample-size テスト用の十分なサイズのデータセット。"""
    return Dataset.from_dict({
        "text": [
            f"This is document number {i}. "
            "It has sufficient length to pass the text length checker "
            "and contains absolutely no quality issues."
            for i in range(n)
        ]
    })


def _dataset_with_html_and_control_chars() -> Dataset:
    """HTMLタグと制御文字を含むデータセット（--fix テスト用）。"""
    return Dataset.from_dict({
        "text": [
            "<p>Hello <b>world</b></p>",
            "Text with\x00control chars",
            "Normal clean text without any issues at all.",
        ]
    })


# ---------------------------------------------------------------------------
# AC-14-01: 正常実行（基本フロー）
# ---------------------------------------------------------------------------

class TestCliNormalExecution:
    """
    IT: evaldataset CLI — 正常実行
    Source: docs/design.md — CLI 受入条件 AC-14-01
    """

    def test_clean_dataset_exits_zero(self):
        """
        AC-14-01: 正常実行（基本フロー）

        Given: 品質問題がないデータセット
        When: evaldataset <DATASET_ID> を実行する
        Then: 終了コード 0 で完了する
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _clean_dataset()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/clean-dataset"])

        # Assert (Then)
        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
        )

    def test_clean_dataset_shows_checker_results(self):
        """
        AC-14-01: 正常実行 — 全チェッカーの結果がコンソールに表示される

        Given: 品質問題がないデータセット
        When: evaldataset <DATASET_ID> を実行する（CliRunner は TTY 非接続 → JSON出力）
        Then: 終了コード 0 で完了し、チェッカー結果が出力に含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _clean_dataset()

        # Act (When)
        # CliRunner は TTY 非接続のため JSON 出力になる (AC-14-03b)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/clean-dataset"])

        # Assert (Then)
        assert result.exit_code == 0
        # JSON 出力に results キーが含まれること（AC-13-02 相当）
        output_data = json.loads(result.output)
        assert "results" in output_data


# ---------------------------------------------------------------------------
# AC-14-01b: 品質問題検出時の終了コード
# ---------------------------------------------------------------------------

class TestCliExitCodesOnIssues:
    """
    IT: evaldataset CLI — 品質問題検出時の終了コード
    Source: docs/design.md — CLI 受入条件 AC-14-01b
    """

    def test_warning_issues_exit_code_1(self):
        """
        AC-14-01b: WARNING のみ含むデータセット → 終了コード 1

        Given: WARNING 以上の Issue を含むデータセット（短すぎるテキスト）
        When: evaldataset <DATASET_ID> を実行する
        Then: 終了コード 1 で終了する
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_warnings()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/warning-dataset"])

        # Assert (Then)
        assert result.exit_code == 1, (
            f"Expected exit code 1 for WARNING issues, got {result.exit_code}. "
            f"Output:\n{result.output}"
        )

    def test_error_issues_exit_code_2(self):
        """
        AC-14-01b: ERROR を含むデータセット → 終了コード 2

        Given: ERROR の Issue を含むデータセット（None フィールド）
        When: evaldataset <DATASET_ID> を実行する
        Then: 終了コード 2 で終了する
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_errors()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/error-dataset"])

        # Assert (Then)
        assert result.exit_code == 2, (
            f"Expected exit code 2 for ERROR issues, got {result.exit_code}. "
            f"Output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# AC-14-02: 不正なデータセット ID でのエラー終了
# ---------------------------------------------------------------------------

class TestCliInvalidDatasetId:
    """
    IT: evaldataset CLI — 不正なデータセット ID でのエラー終了
    Source: docs/design.md — CLI 受入条件 AC-14-02
    """

    def test_nonexistent_dataset_exits_3(self):
        """
        AC-14-02: 不正なデータセット ID でのエラー終了

        Given: 存在しないデータセット ID "nonexistent/dataset-xyz"
        When: evaldataset nonexistent/dataset-xyz を実行する
        Then: 終了コード 3（実行エラー）で終了し、エラーメッセージが出力される
        """
        # Arrange (Given)
        runner = CliRunner()

        # Act (When)
        # モックポリシー: 異常系テストではモック使用可。
        # ここでは load_hf_dataset が例外を送出することをシミュレートする。
        with patch(
            "evaldataset.cli.load_hf_dataset",
            side_effect=Exception("Dataset 'nonexistent/dataset-xyz' not found on Hub"),
        ):
            result = runner.invoke(main, ["nonexistent/dataset-xyz"])

        # Assert (Then)
        assert result.exit_code == 3, (
            f"Expected exit code 3 for nonexistent dataset, got {result.exit_code}. "
            f"Output:\n{result.output}"
        )
        # エラーメッセージが何らかの形で出力される
        assert result.output is not None and len(result.output) > 0, (
            "Expected error message in output"
        )


# ---------------------------------------------------------------------------
# AC-14-03: --output json でのマシン可読出力
# AC-13-02: --output json での summary/results キー
# ---------------------------------------------------------------------------

class TestCliJsonOutput:
    """
    IT: evaldataset CLI — --output json でのマシン可読出力
    Source: docs/design.md — CLI 受入条件 AC-14-03, AC-13-02
    """

    def test_json_output_is_valid_json(self):
        """
        AC-14-03: --output json でのマシン可読出力

        Given: 有効なデータセット ID と --output json オプション
        When: evaldataset <DATASET_ID> --output json を実行する
        Then: stdout に有効な JSON が出力される
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _clean_dataset()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        # Assert (Then)
        # JSON として parse できること
        try:
            output_data = json.loads(result.output)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"stdout is not valid JSON: {exc}\nOutput:\n{result.output}"
            )
        assert output_data is not None

    def test_json_output_contains_summary_and_results_keys(self):
        """
        AC-13-02: --output json での summary / results キー

        Given: 品質問題を含む Dataset と --output json オプション
        When: evaldataset <DATASET_ID> --output json を実行する
        Then: stdout に有効な JSON が出力され、summary と results キーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_warnings()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        # Assert (Then)
        output_data = json.loads(result.output)
        assert "summary" in output_data, (
            f"'summary' key not found in JSON output: {output_data}"
        )
        assert "results" in output_data, (
            f"'results' key not found in JSON output: {output_data}"
        )

    def test_json_output_exit_code_follows_issue_severity(self):
        """
        AC-14-03: --output json 時の exit code は問題の有無に応じて 0/1/2

        Given: WARNING を含む Dataset と --output json オプション
        When: evaldataset <DATASET_ID> --output json を実行する
        Then: exit code は 1（WARNING 検出時）
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_warnings()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        # Assert (Then)
        assert result.exit_code == 1, (
            f"Expected exit code 1 for dataset with WARNING issues only, "
            f"got {result.exit_code}. Output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# AC-14-03b: TTY 非接続時の自動 JSON 出力
# ---------------------------------------------------------------------------

class TestCliTtyAutoJsonOutput:
    """
    IT: evaldataset CLI — TTY 非接続時の自動 JSON 出力
    Source: docs/design.md — CLI 受入条件 AC-14-03b
    """

    def test_non_tty_outputs_json_without_flag(self):
        """
        AC-14-03b: TTY 非接続時の自動 JSON 出力

        Given: 有効なデータセット ID で stdout が TTY でない環境
        When: --output 未指定で evaldataset <DATASET_ID> を実行する
        Then: JSON 形式で stdout に出力される
        """
        # Arrange (Given)
        # CliRunner はデフォルトで TTY 非接続（is_tty=False）
        runner = CliRunner()
        dataset = _clean_dataset()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(main, ["test/dataset"])

        # Assert (Then)
        try:
            output_data = json.loads(result.output)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Expected JSON output in non-TTY mode, but got invalid JSON: {exc}\n"
                f"Output:\n{result.output}"
            )
        assert output_data is not None


# ---------------------------------------------------------------------------
# AC-14-04: --sample-size によるサンプリング
# ---------------------------------------------------------------------------

class TestCliSampleSize:
    """
    IT: evaldataset CLI — --sample-size によるサンプリング
    Source: docs/design.md — CLI 受入条件 AC-14-04
    """

    def test_sample_size_limits_checked_rows(self):
        """
        AC-14-04: --sample-size によるサンプリング

        Given: 1,000 件以上のデータセットと --sample-size 100
        When: evaldataset <DATASET_ID> --sample-size 100 を実行する
        Then: 100 件のサブセットに対してチェックが実行され、
              JSON 出力の total_rows が 100 である

        Note: CLI は load_hf_dataset に CheckerConfig(sample_size=100) を渡す。
        load_hf_dataset がサンプリングを担当するため、モックは
        config.sample_size を読み取って適切なサイズのデータセットを返す。
        """
        # Arrange (Given)
        runner = CliRunner()

        def mock_load_with_sampling(dataset_id, **kwargs):
            config = kwargs.get("config")
            n = config.sample_size if (config and config.sample_size) else 1000
            return Dataset.from_dict({
                "text": [
                    f"Unique document {i}: sufficient length text for quality checking purposes."
                    for i in range(n)
                ]
            })

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", side_effect=mock_load_with_sampling):
            result = runner.invoke(
                main,
                ["test/large-dataset", "--sample-size", "100", "--output", "json"],
            )

        # Assert (Then)
        assert result.exit_code in (0, 1, 2), (
            f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
        )
        output_data = json.loads(result.output)
        # total_rows が top-level に含まれる
        total_rows = (
            output_data.get("total_rows")
            or output_data.get("summary", {}).get("total_rows")
        )
        assert total_rows == 100, (
            f"Expected total_rows=100 after --sample-size 100, got {total_rows}. "
            f"Full output: {output_data}"
        )


# ---------------------------------------------------------------------------
# AC-14-05: --dry-run での変更なし確認
# ---------------------------------------------------------------------------

class TestCliDryRun:
    """
    IT: evaldataset CLI — --dry-run での変更なし確認
    Source: docs/design.md — CLI 受入条件 AC-14-05
    """

    def test_dry_run_does_not_write_files(self):
        """
        AC-14-05: --dry-run での変更なし確認

        Given: 品質問題を含む Dataset と --fix --dry-run オプション
        When: evaldataset <DATASET_ID> --fix --dry-run を実行する
        Then: 修正対象レコード一覧が出力されるが、実際のファイル書き込みは行われない
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_html_and_control_chars()

        with tempfile.TemporaryDirectory() as tmpdir:
            fix_output_path = os.path.join(tmpdir, "fixed_dataset")

            # Act (When)
            with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
                result = runner.invoke(
                    main,
                    [
                        "test/dataset",
                        "--fix",
                        "--dry-run",
                        "--fix-output", fix_output_path,
                    ],
                )

            # Assert (Then)
            # --dry-run なので fix_output_path にファイルが書き込まれない
            assert not os.path.exists(fix_output_path), (
                f"--dry-run should not write files, but {fix_output_path} was created"
            )
            # コマンド自体は正常終了（終了コードはIssueの有無による）
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code} for --dry-run. "
                f"Output:\n{result.output}"
            )

    def test_dry_run_outputs_fix_targets(self):
        """
        AC-14-05: --dry-run — 修正対象レコード一覧が出力される

        Given: HTML タグを含む Dataset と --fix --dry-run オプション
        When: evaldataset <DATASET_ID> --fix --dry-run を実行する
        Then: 何らかの出力が生成される（修正対象の情報）
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_html_and_control_chars()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                ["test/dataset", "--fix", "--dry-run"],
            )

        # Assert (Then)
        assert result.output is not None and len(result.output) > 0, (
            "--dry-run should produce some output"
        )


# ---------------------------------------------------------------------------
# AC-14-06: 制御文字を含む入力の拒否
# ---------------------------------------------------------------------------

class TestCliControlCharacterValidation:
    """
    IT: evaldataset CLI — 制御文字を含む入力の拒否
    Source: docs/design.md — CLI 受入条件 AC-14-06
    """

    def test_control_char_in_dataset_id_rejected(self):
        """
        AC-14-06: 制御文字を含む入力の拒否

        Given: DATASET_ID 引数に制御文字 (\\x00) を含む入力
        When: evaldataset コマンドを実行する
        Then: 終了コード 1 でエラーメッセージが出力され、処理が開始されない
        """
        # Arrange (Given)
        runner = CliRunner()
        malicious_dataset_id = "valid/dataset\x00injected"

        # Act (When)
        # 制御文字の検証はデータセット読み込み前に行われるため、
        # load_hf_dataset はパッチしない（呼ばれないはずなので）
        result = runner.invoke(main, [malicious_dataset_id])

        # Assert (Then)
        assert result.exit_code == 1, (
            f"Expected exit code 1 for control character in DATASET_ID, "
            f"got {result.exit_code}. Output:\n{result.output}"
        )
        assert result.output is not None and len(result.output) > 0, (
            "Expected error message in output"
        )

    def test_other_control_chars_in_dataset_id_rejected(self):
        """
        AC-14-06: 制御文字を含む入力の拒否（\\x08 のケース）

        Given: DATASET_ID 引数に制御文字 (\\x08) を含む入力
        When: evaldataset コマンドを実行する
        Then: 終了コード 1 でエラーメッセージが出力され、処理が開始されない
        """
        # Arrange (Given)
        runner = CliRunner()
        malicious_dataset_id = "valid/dataset\x08injected"

        # Act (When)
        result = runner.invoke(main, [malicious_dataset_id])

        # Assert (Then)
        assert result.exit_code == 1, (
            f"Expected exit code 1 for control character in DATASET_ID, "
            f"got {result.exit_code}. Output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# AC-13-03: リッチコンソール出力（デフォルト、TTY 接続時）
# ---------------------------------------------------------------------------

class TestCliRichOutput:
    """
    IT: evaldataset CLI — リッチコンソール出力（TTY 接続時）
    Source: docs/design.md — レポート受入条件 AC-13-03
    """

    def test_rich_output_flag_produces_output(self):
        """
        AC-13-03: リッチコンソール出力（--output rich 明示指定）

        Given: 品質問題を含む Dataset と --output rich オプション
        When: evaldataset <DATASET_ID> --output rich を実行する
        Then: 何らかの出力が生成される（チェッカー結果を含む表示）

        Note: CliRunner は TTY 非接続のため実際の Rich テーブルは描画されない場合がある。
        TTY 接続時の Rich テーブル表示は CLI 設計書のデータフロー
        (RichReporter / TTY 接続時) に基づく。このテストは
        --output rich フラグが認識されて何らかの出力が生成されることを確認する。
        """
        # Arrange (Given)
        runner = CliRunner()
        dataset = _dataset_with_warnings()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                ["test/dataset", "--output", "rich"],
                color=False,
            )

        # Assert (Then)
        # 何らかの出力が生成されること
        assert result.output is not None and len(result.output.strip()) > 0, (
            "--output rich should produce some output"
        )
        # exit code は issue の有無に応じて 0/1/2
        assert result.exit_code in (0, 1, 2), (
            f"Unexpected exit code {result.exit_code} for --output rich. "
            f"Output:\n{result.output}"
        )
