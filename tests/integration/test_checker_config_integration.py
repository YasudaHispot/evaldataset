"""Integration tests for CheckerConfig — YAML loading and CLI integration.

IT: CheckerConfig
Source: docs/design.md — CheckerConfig と YAML 設定ファイル 受入条件
        (AC-15-01, AC-15-02, AC-15-03, AC-15-04)
"""

import json

import pytest
from click.testing import CliRunner
from datasets import Dataset
from unittest.mock import patch

from evaldataset.cli import main
from evaldataset.config import CheckerConfig


# ---------------------------------------------------------------------------
# テスト用データセットファクトリ
# ---------------------------------------------------------------------------


def _dataset_with_long_text(char_count: int) -> Dataset:
    """指定文字数のテキストを1件含み、正常な短いテキストを1件含むデータセット。"""
    return Dataset.from_dict({
        "text": [
            "x" * char_count,
            "This is a normal document with sufficient text length for quality checks.",
        ]
    })


def _near_duplicate_dataset() -> Dataset:
    """near-duplicate チェッカーが検出するような類似テキストペアを含むデータセット。

    1文字だけ違う極めて類似したテキストペア。NearDuplicateChecker が
    実行された場合は WARNING を検出する。
    """
    base = "word " * 100  # 100語の同一内容
    variant = base[:-1] + "X"  # 最後の1文字だけ違う
    return Dataset.from_dict({"text": [base, variant]})


# ---------------------------------------------------------------------------
# AC-15-01: YAML ファイルからの設定読み込み
# ---------------------------------------------------------------------------


class TestCheckerConfigFromYaml:
    """
    IT: CheckerConfig — YAML ファイルからの設定読み込み
    Source: docs/design.md — CheckerConfig と YAML 設定ファイル 受入条件 (AC-15-01)
    """

    def test_yaml_overrides_min_length_and_keeps_defaults(self, tmp_path):
        """
        AC-15-01: YAML ファイルからの設定読み込み

        Given: min_length: 100 を含む YAML ファイル
        When: CheckerConfig.from_yaml(path) を実行する
        Then: config.min_length == 100 であり、他のフィールドはデフォルト値のままである
        """
        # Arrange (Given)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("min_length: 100\n")

        # Act (When)
        config = CheckerConfig.from_yaml(str(config_file))

        # Assert (Then)
        assert config.min_length == 100, (
            f"Expected min_length=100, got {config.min_length}"
        )
        # 他のフィールドはデフォルト値のまま
        default = CheckerConfig()
        assert config.max_length == default.max_length, (
            f"Expected max_length={default.max_length} (default), got {config.max_length}"
        )
        assert config.languages == default.languages, (
            f"Expected languages={default.languages} (default), got {config.languages}"
        )
        assert config.minhash_threshold == default.minhash_threshold, (
            f"Expected minhash_threshold={default.minhash_threshold} (default), "
            f"got {config.minhash_threshold}"
        )
        assert config.skip_checkers == default.skip_checkers, (
            f"Expected skip_checkers={default.skip_checkers} (default), "
            f"got {config.skip_checkers}"
        )


# ---------------------------------------------------------------------------
# AC-15-02: 未知キーの無視
# ---------------------------------------------------------------------------


class TestCheckerConfigUnknownKeys:
    """
    IT: CheckerConfig — 未知キーの無視
    Source: docs/design.md — CheckerConfig と YAML 設定ファイル 受入条件 (AC-15-02)
    """

    def test_unknown_key_is_ignored_without_error(self, tmp_path):
        """
        AC-15-02: 未知キーの無視

        Given: CheckerConfig に存在しないキー unknown_key: value を含む YAML ファイル
        When: CheckerConfig.from_yaml(path) を実行する
        Then: エラーなく読み込まれ、既知フィールドのみが設定される
        """
        # Arrange (Given)
        config_file = tmp_path / "config_with_unknown.yaml"
        config_file.write_text(
            "unknown_key: some_value\n"
            "another_unknown: 42\n"
            "min_length: 75\n"
        )

        # Act (When) — エラーが発生しないこと自体を検証する
        config = CheckerConfig.from_yaml(str(config_file))

        # Assert (Then)
        # 既知フィールドは正しく設定される
        assert config.min_length == 75, (
            f"Expected min_length=75, got {config.min_length}"
        )
        # 未知キーは CheckerConfig オブジェクトの属性として存在しない
        assert not hasattr(config, "unknown_key"), (
            "unknown_key should not be set as an attribute on CheckerConfig"
        )
        assert not hasattr(config, "another_unknown"), (
            "another_unknown should not be set as an attribute on CheckerConfig"
        )

    def test_only_unknown_keys_loads_all_defaults(self, tmp_path):
        """
        AC-15-02: 未知キーのみの YAML ファイル — 全フィールドがデフォルト値

        Given: 既知フィールドを含まず未知キーのみの YAML ファイル
        When: CheckerConfig.from_yaml(path) を実行する
        Then: エラーなく読み込まれ、全フィールドがデフォルト値のままである
        """
        # Arrange (Given)
        config_file = tmp_path / "unknown_only.yaml"
        config_file.write_text("totally_unknown_field: hello\n")

        # Act (When)
        config = CheckerConfig.from_yaml(str(config_file))

        # Assert (Then)
        default = CheckerConfig()
        assert config.min_length == default.min_length
        assert config.max_length == default.max_length
        assert config.skip_checkers == default.skip_checkers


# ---------------------------------------------------------------------------
# AC-15-03: --config オプションでの CLI 連携
# ---------------------------------------------------------------------------


class TestCheckerConfigCliIntegration:
    """
    IT: CheckerConfig — --config オプションでの CLI 連携
    Source: docs/design.md — CheckerConfig と YAML 設定ファイル 受入条件 (AC-15-03)
    """

    def test_config_yaml_max_length_causes_warning_for_exceeding_text(self, tmp_path):
        """
        AC-15-03: --config オプションでの CLI 連携

        Given: max_length: 5000 を含む YAML ファイルと --config オプション
        When: evaldataset <DATASET_ID> --config path/to/config.yaml を実行する
        Then: TextLengthChecker が 5,001 文字のテキストを WARNING として検出する
        """
        # Arrange (Given)
        config_file = tmp_path / "custom_config.yaml"
        config_file.write_text("max_length: 5000\n")

        # 5,001 文字のテキストを含むデータセット（max_length=5000 を超過する）
        dataset = _dataset_with_long_text(5001)

        runner = CliRunner()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--config", str(config_file),
                    "--output", "json",
                ],
            )

        # Assert (Then)
        assert result.exit_code in (1, 2), (
            f"Expected exit code 1 or 2 (issues detected), got {result.exit_code}. "
            f"Output:\n{result.output}"
        )
        output_data = json.loads(result.output)

        # TextLengthChecker の結果が WARNING を含むこと
        results = output_data.get("results", [])
        text_length_results = [
            r for r in results
            if "text_length" in r.get("checker", "").lower()
            or "textlength" in r.get("checker", "").lower()
        ]
        assert len(text_length_results) > 0, (
            f"TextLengthChecker result not found in output. Results: {results}"
        )
        text_length_result = text_length_results[0]

        # issues に WARNING が含まれること
        issues = text_length_result.get("issues", [])
        warning_issues = [
            i for i in issues
            if i.get("severity", "").upper() == "WARNING"
        ]
        assert len(warning_issues) > 0, (
            f"Expected WARNING issue from TextLengthChecker for 5001-char text "
            f"with max_length=5000. issues: {issues}"
        )

    def test_config_yaml_max_length_no_warning_for_within_limit_text(self, tmp_path):
        """
        AC-15-03 補足: max_length: 5000 の設定で 5,000 文字のテキストは WARNING なし

        Given: max_length: 5000 を含む YAML ファイルと --config オプション
        When: 5,000 文字のテキスト（境界値）で実行する
        Then: TextLengthChecker が WARNING を発生させない
        """
        # Arrange (Given)
        config_file = tmp_path / "custom_config.yaml"
        config_file.write_text("max_length: 5000\n")

        # ちょうど 5,000 文字（境界値 = 許容範囲内）のデータセット
        dataset = _dataset_with_long_text(5000)

        runner = CliRunner()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--config", str(config_file),
                    "--output", "json",
                ],
            )

        # Assert (Then)
        output_data = json.loads(result.output)
        results = output_data.get("results", [])
        text_length_results = [
            r for r in results
            if "text_length" in r.get("checker", "").lower()
            or "textlength" in r.get("checker", "").lower()
        ]
        assert len(text_length_results) > 0, (
            f"TextLengthChecker result not found in output. Results: {results}"
        )
        text_length_result = text_length_results[0]
        issues = text_length_result.get("issues", [])
        max_length_warnings = [
            i for i in issues
            if i.get("severity", "").upper() == "WARNING"
        ]
        assert len(max_length_warnings) == 0, (
            f"Expected no WARNING for 5000-char text with max_length=5000, "
            f"got: {max_length_warnings}"
        )


# ---------------------------------------------------------------------------
# AC-15-04: skip_checkers によるチェッカースキップ
# ---------------------------------------------------------------------------


class TestCheckerConfigSkipCheckers:
    """
    IT: CheckerConfig — skip_checkers によるチェッカースキップ
    Source: docs/design.md — CheckerConfig と YAML 設定ファイル 受入条件 (AC-15-04)
    """

    def test_skip_near_duplicate_checker_via_yaml(self, tmp_path):
        """
        AC-15-04: skip_checkers によるチェッカースキップ

        Given: skip_checkers: ["near_duplicate"] の設定
        When: チェックを実行する
        Then: NearDuplicateChecker が実行されず、Report にそのチェッカーの結果が含まれない
        """
        # Arrange (Given)
        config_file = tmp_path / "skip_config.yaml"
        config_file.write_text('skip_checkers:\n  - "near_duplicate"\n')

        # 類似テキストを含むデータセット（NearDuplicateChecker が実行されれば WARNING が出る）
        dataset = _near_duplicate_dataset()

        runner = CliRunner()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--config", str(config_file),
                    "--output", "json",
                ],
            )

        # Assert (Then)
        assert result.exit_code in (0, 1, 2), (
            f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
        )
        output_data = json.loads(result.output)

        # NearDuplicateChecker の結果が Report に含まれないこと
        results = output_data.get("results", [])
        near_dup_results = [
            r for r in results
            if "near_duplicate" in r.get("checker", "").lower()
            or "neardup" in r.get("checker", "").lower()
            or "near_dup" in r.get("checker", "").lower()
        ]
        assert len(near_dup_results) == 0, (
            f"NearDuplicateChecker should be skipped but found results: {near_dup_results}"
        )

    def test_skip_near_duplicate_checker_via_cli_option(self):
        """
        AC-15-04 補足: --skip-checker CLI オプションによるチェッカースキップ

        Given: --skip-checker near_duplicate オプション
        When: チェックを実行する
        Then: NearDuplicateChecker が実行されず、Report にそのチェッカーの結果が含まれない

        Note: CLI オプション --skip-checker は YAML の skip_checkers と同等の動作をする
        （設定マージ優先順位: CLI > YAML > デフォルト）
        """
        # Arrange (Given)
        dataset = _near_duplicate_dataset()
        runner = CliRunner()

        # Act (When)
        with patch("evaldataset.cli.load_hf_dataset", return_value=dataset):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--skip-checker", "near_duplicate",
                    "--output", "json",
                ],
            )

        # Assert (Then)
        assert result.exit_code in (0, 1, 2), (
            f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
        )
        output_data = json.loads(result.output)

        results = output_data.get("results", [])
        near_dup_results = [
            r for r in results
            if "near_duplicate" in r.get("checker", "").lower()
            or "neardup" in r.get("checker", "").lower()
            or "near_dup" in r.get("checker", "").lower()
        ]
        assert len(near_dup_results) == 0, (
            f"NearDuplicateChecker should be skipped via --skip-checker but "
            f"found results: {near_dup_results}"
        )
