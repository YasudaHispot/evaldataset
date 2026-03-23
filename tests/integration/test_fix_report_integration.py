"""Integration tests for fix before/after report via CLI.

IT: 修正前後レポート
Source: docs/design.md — 修正前後レポート 受入条件 (AC-17-01, AC-17-02, AC-17-03)

修正前後レポートは `--fix` / `--dry-run` 実行時に、修正前後のチェック結果を
表示し改善度を可視化する。

テスト方法:
- CliRunner + isolated_filesystem() でカレントディレクトリを制御する
  (--fix-output は CWD 内のパスのみ許可されるため)
- `--output json` で JSON 出力を取得し before / after 構造を検証する
- WARNING を含むデータセット: 短文テキスト（min_length=50 未満）1 件
  + 正常テキスト 2 件（各テキストはユニーク・重複なし）
"""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner
from datasets import Dataset, disable_progress_bars

from evaldataset.cli import main

# Suppress HuggingFace progress bars in test output.
disable_progress_bars()

# ---------------------------------------------------------------------------
# Shared text constants
# ---------------------------------------------------------------------------

# 短文テキスト: min_length=50 未満 → TextLengthChecker が WARNING を検出する
_SHORT_TEXT = "Short text."

# 正常テキスト: min_length=50 以上、互いに内容が異なりユニーク
_NORMAL_TEXT_A = (
    "Machine learning algorithms process large amounts of data efficiently "
    "and enable computers to learn patterns from experience without explicit programming."
)
_NORMAL_TEXT_B = (
    "Natural language processing enables computers to understand and generate "
    "human language, transforming how we interact with technology every day."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parquet_dataset(ds: Dataset, base_dir: str, subdir: str = "input") -> str:
    """Persist *ds* as Parquet inside *base_dir/<subdir>/data/* and return the
    relative data path (relative to *base_dir*).

    The relative path is used as DATASET_ID for CLI invocation inside
    isolated_filesystem(), where CWD == base_dir.
    """
    data_dir = os.path.join(base_dir, subdir, "data")
    os.makedirs(data_dir, exist_ok=True)
    ds.to_parquet(os.path.join(data_dir, "train-00000-of-00001.parquet"))
    return os.path.join(subdir, "data")


# ---------------------------------------------------------------------------
# AC-17-01: --fix --output json で修正前後レポートが出力される
# ---------------------------------------------------------------------------


class TestFixReportJson:
    """
    IT: 修正前後レポート — --fix --output json
    Source: docs/design.md — 修正前後レポート 受入条件 AC-17-01
    """

    def test_fix_json_output_contains_before_and_after_keys(self):
        """
        AC-17-01: --fix --output json で修正前後レポートが出力される（before/after キー）

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: JSON 出力に before と after キーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            output_data = json.loads(result.output)

            assert "before" in output_data, (
                f"'before' key not found in JSON output: {list(output_data.keys())}"
            )
            assert "after" in output_data, (
                f"'after' key not found in JSON output: {list(output_data.keys())}"
            )

    def test_fix_json_before_has_warnings(self):
        """
        AC-17-01: 修正前 before.summary.warnings が 0 より大きい

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: before.summary.warnings > 0 である
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            before = output_data.get("before", {})
            before_summary = before.get("summary", {})
            before_warnings = before_summary.get("warnings", 0)

            assert before_warnings > 0, (
                f"Expected before.summary.warnings > 0 for dataset with short text, "
                f"got {before_warnings}. before.summary: {before_summary}"
            )

    def test_fix_json_after_warnings_le_before_warnings(self):
        """
        AC-17-01: 修正後 after.summary.warnings が修正前以下である

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: after.summary.warnings <= before.summary.warnings である
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            before_warnings = output_data["before"]["summary"].get("warnings", 0)
            after_warnings = output_data["after"]["summary"].get("warnings", 0)

            assert after_warnings <= before_warnings, (
                f"Expected after.summary.warnings ({after_warnings}) <= "
                f"before.summary.warnings ({before_warnings})"
            )

    def test_fix_json_output_contains_fix_stats(self):
        """
        AC-17-01: JSON 出力に fix_stats キーが存在する

        Given: WARNING を含む Dataset と --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: JSON 出力に fix_stats キーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            assert "fix_stats" in output_data, (
                f"'fix_stats' key not found in JSON output: {list(output_data.keys())}"
            )

    def test_fix_json_before_has_results_key(self):
        """
        AC-17-01: before オブジェクトに results キーが含まれる

        Given: WARNING を含む Dataset と --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: before.results が存在する
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            before = output_data.get("before", {})
            assert "results" in before, (
                f"'results' key not found in before: {list(before.keys())}"
            )

    def test_fix_json_after_has_results_key(self):
        """
        AC-17-01: after オブジェクトに results キーが含まれる

        Given: WARNING を含む Dataset と --fix --fix-output <PATH> --output json オプション
        When: CLI を実行する
        Then: after.results が存在する
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            after = output_data.get("after", {})
            assert "results" in after, (
                f"'results' key not found in after: {list(after.keys())}"
            )


# ---------------------------------------------------------------------------
# AC-17-02: --dry-run --output json で修正前後レポートが出力される
# ---------------------------------------------------------------------------


class TestDryRunReportJson:
    """
    IT: 修正前後レポート — --fix --dry-run --output json
    Source: docs/design.md — 修正前後レポート 受入条件 AC-17-02
    """

    def test_dry_run_json_output_contains_before_and_after_keys(self):
        """
        AC-17-02: --dry-run --output json で修正前後レポートが出力される（before/after キー）

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --dry-run --output json オプション
        When: CLI を実行する
        Then: JSON 出力に before と after キーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--dry-run",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            output_data = json.loads(result.output)

            assert "before" in output_data, (
                f"'before' key not found in JSON output: {list(output_data.keys())}"
            )
            assert "after" in output_data, (
                f"'after' key not found in JSON output: {list(output_data.keys())}"
            )

    def test_dry_run_does_not_write_fix_output_file(self):
        """
        AC-17-02: --dry-run 時にファイル出力は行われない

        Given: WARNING を含む Dataset と --fix --dry-run --output json オプション
        When: CLI を実行する
        Then: --fix-output で指定したパスにファイルが作成されていない
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output_dry_run"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--dry-run",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            assert not os.path.exists(fix_dir), (
                f"--dry-run should not write files, but '{fix_dir}' was created"
            )

    def test_dry_run_json_before_has_summary(self):
        """
        AC-17-02: --dry-run JSON 出力の before に summary が含まれる

        Given: WARNING を含む Dataset と --fix --dry-run --output json オプション
        When: CLI を実行する
        Then: before.summary が存在する
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output_dry_run"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--dry-run",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            before = output_data.get("before", {})
            assert "summary" in before, (
                f"'summary' not found in before: {list(before.keys())}"
            )

    def test_dry_run_json_after_has_summary(self):
        """
        AC-17-02: --dry-run JSON 出力の after に summary が含まれる

        Given: WARNING を含む Dataset と --fix --dry-run --output json オプション
        When: CLI を実行する
        Then: after.summary が存在する
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output_dry_run"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--dry-run",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            after = output_data.get("after", {})
            assert "summary" in after, (
                f"'summary' not found in after: {list(after.keys())}"
            )


# ---------------------------------------------------------------------------
# AC-17-03: --fix で Rich 修正前後レポートが表示される
# ---------------------------------------------------------------------------


class TestFixReportRich:
    """
    IT: 修正前後レポート — --fix Rich コンソール出力
    Source: docs/design.md — 修正前後レポート 受入条件 AC-17-03
    """

    def test_fix_rich_output_contains_before_section(self):
        """
        AC-17-03: --fix で Rich 修正前後レポートが表示される（Before セクション）

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> オプション（--output 未指定）
        When: CLI を実行する
        Then: コンソール出力に修正前（Before）のサマリーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            # --output 未指定 (TTY 非接続時は自動 JSON、--output rich 明示で Rich 出力)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "rich"],
                color=False,
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            assert result.output is not None and len(result.output.strip()) > 0, (
                "--fix --output rich should produce some output"
            )
            # 修正前（Before）に関する表示が含まれること
            assert "before" in result.output.lower() or "Before" in result.output, (
                f"Expected 'before' or 'Before' in Rich output, got:\n{result.output}"
            )

    def test_fix_rich_output_contains_after_section(self):
        """
        AC-17-03: --fix で Rich 修正前後レポートが表示される（After セクション）

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> オプション（--output 未指定）
        When: CLI を実行する
        Then: コンソール出力に修正後（After）のサマリーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "rich"],
                color=False,
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            # 修正後（After）に関する表示が含まれること
            assert "after" in result.output.lower() or "After" in result.output, (
                f"Expected 'after' or 'After' in Rich output, got:\n{result.output}"
            )

    def test_fix_rich_output_shows_improvement(self):
        """
        AC-17-03: --fix Rich 出力に改善された項目が確認できる

        Given: WARNING を含む Dataset（短文テキスト 1 件 + 正常テキスト 2 件）と
               --fix --fix-output <PATH> オプション（--output rich 指定）
        When: CLI を実行する
        Then: コンソール出力が生成され、修正の前後に関する情報が含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_SHORT_TEXT, _NORMAL_TEXT_A, _NORMAL_TEXT_B]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "rich"],
                color=False,
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            # Before と After の両方のキーワードが出力中に存在すること
            output_lower = result.output.lower()
            has_before = "before" in output_lower
            has_after = "after" in output_lower
            assert has_before and has_after, (
                f"Expected both 'before' and 'after' in Rich output. "
                f"has_before={has_before}, has_after={has_after}. "
                f"Output:\n{result.output}"
            )
