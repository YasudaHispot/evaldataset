"""Unit tests for evaldataset CLI command.

Covers:
- AC-14-01: 正常実行 — 終了コード 0、全チェッカー結果がコンソールに表示
- AC-14-01b: 品質問題検出時の終了コード — WARNING: 1、ERROR: 2
- AC-14-02: 不正なデータセットIDでのエラー終了 — 終了コード 3、stderrにエラー
- AC-14-03: --output json でのマシン可読出力 — stdoutに有効なJSON
- AC-14-03b: TTY非接続時の自動JSON出力 — --output json 未指定でもJSON
- AC-14-04: --sample-size によるサンプリング — sample_size が config に渡される
- AC-14-05: --dry-run での変更なし確認
- AC-14-06: 制御文字を含む入力の拒否 — 終了コード 1
- --skip-checker のテスト
- --config YAMLファイル読み込みのテスト
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from datasets import Dataset

from evaldataset.models import (
    CheckResult,
    Issue,
    Report,
    Severity,
)


# ---------------------------------------------------------------------------
# ヘルパー: テスト用データ生成
# ---------------------------------------------------------------------------


def _make_dataset(texts: list[str]) -> Dataset:
    """テスト用のシンプルなDatasetを作成する。"""
    return Dataset.from_dict({"text": texts})


def _make_check_result(
    checker_name: str = "test_checker",
    issues: list[Issue] | None = None,
) -> CheckResult:
    return CheckResult(
        checker_name=checker_name,
        issues=issues or [],
        stats={},
    )


def _make_report(
    dataset_id: str = "test/dataset",
    total_rows: int = 5,
    results: list[CheckResult] | None = None,
) -> Report:
    return Report(
        dataset_id=dataset_id,
        split="train",
        total_rows=total_rows,
        text_field="text",
        results=results or [],
    )


def _make_warning_issue(checker: str = "test") -> Issue:
    return Issue(
        checker=checker,
        severity=Severity.WARNING,
        message="Test warning",
        row_indices=[0],
        details={},
    )


def _make_error_issue(checker: str = "test") -> Issue:
    return Issue(
        checker=checker,
        severity=Severity.ERROR,
        message="Test error",
        row_indices=[0],
        details={},
    )


def _make_mock_checker(result: CheckResult):
    """指定されたCheckResultを返すモックチェッカーを作成する。"""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.check.return_value = result
    mock_cls.return_value = mock_instance
    mock_cls.name = result.checker_name
    return mock_cls


# ---------------------------------------------------------------------------
# AC-14-01: 正常実行（基本フロー）— 終了コード 0
# ---------------------------------------------------------------------------


class TestCliNormalExecution:
    """CLIの正常実行テスト。"""

    def test_exit_code_0_when_no_issues(self) -> None:
        """AC-14-01: 品質問題なしのデータセットで終了コード 0 で完了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["Hello world", "Good text", "Nice content"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 0

    def test_exits_cleanly_with_valid_dataset_id(self) -> None:
        """AC-14-01: 有効なデータセットIDでCLIが正常終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["sample text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["user/my-dataset", "--output", "json"])

        assert result.exit_code == 0

    def test_all_checker_results_included_in_output(self) -> None:
        """AC-14-01: 全チェッカーの結果が出力に含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["sample text"])

        mock_schema_checker = MagicMock()
        mock_schema_checker.return_value.check.return_value = _make_check_result(
            checker_name="schema", issues=[]
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"schema": mock_schema_checker},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        checker_names = [r["checker"] for r in parsed["results"]]
        assert "schema" in checker_names


# ---------------------------------------------------------------------------
# AC-14-01b: 品質問題検出時の終了コード
# ---------------------------------------------------------------------------


class TestCliExitCodes:
    """CLIの終了コードに関するテスト。"""

    def test_exit_code_1_when_warning_only(self) -> None:
        """AC-14-01b: WARNINGのみの場合、終了コード 1 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        mock_checker_cls = MagicMock()
        mock_checker_cls.return_value.check.return_value = _make_check_result(
            checker_name="text_length",
            issues=[_make_warning_issue(checker="text_length")],
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"text_length": mock_checker_cls},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 1

    def test_exit_code_2_when_error_detected(self) -> None:
        """AC-14-01b: ERRORがある場合、終了コード 2 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        mock_checker_cls = MagicMock()
        mock_checker_cls.return_value.check.return_value = _make_check_result(
            checker_name="schema",
            issues=[_make_error_issue(checker="schema")],
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"schema": mock_checker_cls},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 2

    def test_exit_code_2_when_both_error_and_warning(self) -> None:
        """AC-14-01b: ERRORとWARNINGが混在する場合、終了コード 2 で終了する（ERRORが優先）。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        mock_checker_cls = MagicMock()
        mock_checker_cls.return_value.check.return_value = _make_check_result(
            checker_name="schema",
            issues=[
                _make_error_issue(checker="schema"),
                _make_warning_issue(checker="schema"),
            ],
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"schema": mock_checker_cls},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 2

    def test_exit_code_0_when_only_info_issues(self) -> None:
        """INFO のみの Issue は WARNING/ERROR として扱わない。終了コード 0 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        info_issue = Issue(
            checker="boilerplate",
            severity=Severity.INFO,
            message="Boilerplate detected",
            row_indices=[0],
            details={},
        )
        mock_checker_cls = MagicMock()
        mock_checker_cls.return_value.check.return_value = _make_check_result(
            checker_name="boilerplate",
            issues=[info_issue],
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"boilerplate": mock_checker_cls},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        # INFO は終了コード1/2の対象外なので 0 で終了
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# AC-14-02: 不正なデータセットIDでのエラー終了
# ---------------------------------------------------------------------------


class TestCliInvalidDatasetId:
    """不正なデータセットIDでのエラー処理テスト。"""

    def test_exit_code_3_when_dataset_not_found(self) -> None:
        """AC-14-02: 存在しないデータセットIDで終了コード 3 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()

        with patch(
            "evaldataset.cli.load_hf_dataset",
            side_effect=Exception("Dataset 'nonexistent/dataset-xyz' not found"),
        ):
            result = runner.invoke(main, ["nonexistent/dataset-xyz", "--output", "json"])

        assert result.exit_code == 3

    def test_error_message_written_to_stderr_on_load_failure(self) -> None:
        """AC-14-02: データセット読み込み失敗時にエラーメッセージが出力される。"""
        from evaldataset.cli import main

        runner = CliRunner()

        with patch(
            "evaldataset.cli.load_hf_dataset",
            side_effect=ValueError("Invalid dataset ID format"),
        ):
            result = runner.invoke(main, ["bad-dataset-id", "--output", "json"])

        assert result.exit_code == 3
        # 出力（stdout/stderr）にエラーメッセージが含まれること
        assert result.output  # 出力が空でないこと

    def test_exit_code_3_on_connection_error(self) -> None:
        """AC-14-02: ネットワークエラーで終了コード 3 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()

        with patch(
            "evaldataset.cli.load_hf_dataset",
            side_effect=ConnectionError("Network unreachable"),
        ):
            result = runner.invoke(main, ["user/dataset", "--output", "json"])

        assert result.exit_code == 3

    def test_error_in_json_format_when_output_json(self) -> None:
        """AC-14-02: --output json 指定時、エラーもJSON形式で出力される。"""
        from evaldataset.cli import main

        runner = CliRunner()

        stderr_capture = StringIO()
        with patch(
            "evaldataset.cli.load_hf_dataset",
            side_effect=Exception("Load failed"),
        ), patch("sys.stderr", stderr_capture):
            result = runner.invoke(main, ["bad/dataset", "--output", "json"])

        assert result.exit_code == 3
        # stderrにJSONエラーが出力されること
        stderr_capture.seek(0)
        stderr_content = stderr_capture.read()
        if stderr_content:
            parsed_err = json.loads(stderr_content)
            assert "error" in parsed_err


# ---------------------------------------------------------------------------
# AC-14-03: --output json でのマシン可読出力
# ---------------------------------------------------------------------------


class TestCliJsonOutput:
    """--output json オプションのテスト。"""

    def test_output_json_produces_valid_json(self) -> None:
        """AC-14-03: --output json で有効なJSONが stdout に出力される。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 0
        # stdoutからJSONをパースできること
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_output_json_contains_summary_key(self) -> None:
        """AC-14-03: JSON出力に 'summary' キーが含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        parsed = json.loads(result.output)
        assert "summary" in parsed

    def test_output_json_contains_results_key(self) -> None:
        """AC-14-03: JSON出力に 'results' キーが含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        parsed = json.loads(result.output)
        assert "results" in parsed

    def test_output_json_contains_dataset_id(self) -> None:
        """AC-14-03: JSON出力に正しい dataset_id が含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["user/my-dataset", "--output", "json"])

        parsed = json.loads(result.output)
        assert parsed["dataset_id"] == "user/my-dataset"

    def test_output_json_exit_code_1_on_warnings(self) -> None:
        """AC-14-03: --output json でもWARNINGがある場合は終了コード 1 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        mock_checker_cls = MagicMock()
        mock_checker_cls.return_value.check.return_value = _make_check_result(
            checker_name="checker",
            issues=[_make_warning_issue()],
        )

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"checker": mock_checker_cls},
             ):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code == 1
        # それでもJSON出力はされること
        parsed = json.loads(result.output)
        assert "summary" in parsed

    def test_output_json_contains_total_rows(self) -> None:
        """AC-14-03: JSON出力に total_rows が含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text1", "text2", "text3"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        parsed = json.loads(result.output)
        assert parsed["total_rows"] == 3


# ---------------------------------------------------------------------------
# AC-14-03b: TTY非接続時の自動JSON出力
# ---------------------------------------------------------------------------


class TestCliTtyDetection:
    """TTY非接続時の自動JSON出力テスト。"""

    def test_auto_json_when_not_tty(self) -> None:
        """AC-14-03b: TTY非接続時に --output json 未指定でもJSON形式で出力される。"""
        from evaldataset.cli import main

        # CliRunner はデフォルトで TTY ではない（isatty() → False）
        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset"])

        # TTY非接続なので JSON 出力になること
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_auto_json_when_not_tty_contains_summary(self) -> None:
        """AC-14-03b: TTY非接続時の自動JSON出力に 'summary' キーが含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset"])

        parsed = json.loads(result.output)
        assert "summary" in parsed

    def test_auto_json_when_not_tty_contains_results(self) -> None:
        """AC-14-03b: TTY非接続時の自動JSON出力に 'results' キーが含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset"])

        parsed = json.loads(result.output)
        assert "results" in parsed


# ---------------------------------------------------------------------------
# AC-14-04: --sample-size によるサンプリング
# ---------------------------------------------------------------------------


class TestCliSampleSize:
    """--sample-size オプションのテスト。"""

    def test_sample_size_passed_to_config(self) -> None:
        """AC-14-04: --sample-size が CheckerConfig.sample_size に渡される。"""
        from evaldataset.cli import main
        from evaldataset.config import CheckerConfig

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"] * 10)
        captured_config: list[CheckerConfig] = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main, ["test/dataset", "--sample-size", "100", "--output", "json"]
            )

        assert result.exit_code == 0
        assert len(captured_config) == 1
        assert captured_config[0].sample_size == 100

    def test_sample_size_not_set_by_default(self) -> None:
        """AC-14-04: --sample-size 未指定時は config.sample_size が None である。"""
        from evaldataset.cli import main
        from evaldataset.config import CheckerConfig

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config: list[CheckerConfig] = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert len(captured_config) == 1
        assert captured_config[0].sample_size is None

    def test_sample_size_integer_value_accepted(self) -> None:
        """AC-14-04: --sample-size に整数値を指定できる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main, ["test/dataset", "--sample-size", "500", "--output", "json"]
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# AC-14-05: --dry-run での変更なし確認
# ---------------------------------------------------------------------------


class TestCliDryRun:
    """--dry-run オプションのテスト。"""

    def test_dry_run_does_not_save_to_disk(self) -> None:
        """AC-14-05: --fix --dry-run では save_to_disk が呼ばれない。"""
        from evaldataset.cli import main

        runner = CliRunner()
        fix_stats = {"total_fixed": 1, "total_rows": 2}

        # TextCleaner.fix_dataset の戻り値をMagicMockにして save_to_disk を追跡する
        mock_cleaned_dataset = MagicMock()

        with patch("evaldataset.cli.load_hf_dataset", return_value=_make_dataset(["<p>Hello</p>", "Normal text"])), \
             patch("evaldataset.cli.get_all_checkers", return_value={}), \
             patch("evaldataset.cli.TextCleaner") as mock_cleaner_cls:
            mock_cleaner = MagicMock()
            mock_cleaner_cls.return_value = mock_cleaner
            mock_cleaner.fix_dataset.return_value = (mock_cleaned_dataset, fix_stats)

            result = runner.invoke(
                main,
                ["test/dataset", "--fix", "--dry-run", "--output", "json"],
            )

        assert result.exit_code in (0, 1, 2)
        # --dry-run なので save_to_disk は呼ばれない
        mock_cleaned_dataset.save_to_disk.assert_not_called()
        # TextCleaner.fix_dataset は呼ばれる（dry-run でも内部では実行する）
        mock_cleaner.fix_dataset.assert_called_once()

    def test_dry_run_exits_without_runtime_error(self) -> None:
        """AC-14-05: --dry-run は終了コード 3 以外で終了する（実行エラーなし）。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["<p>Hello</p>"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}), \
             patch("evaldataset.cli.TextCleaner") as mock_cleaner_cls:
            mock_cleaner = MagicMock()
            mock_cleaner_cls.return_value = mock_cleaner
            mock_cleaner.fix_dataset.return_value = (
                mock_dataset,
                {"total_fixed": 0, "total_rows": 1},
            )
            result = runner.invoke(
                main, ["test/dataset", "--fix", "--dry-run", "--output", "json"]
            )

        assert result.exit_code != 3

    def test_dry_run_without_fix_flag(self) -> None:
        """AC-14-05: --dry-run のみ（--fix なし）でもエラーにならない。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}), \
             patch("evaldataset.cli.TextCleaner") as mock_cleaner_cls:
            mock_cleaner = MagicMock()
            mock_cleaner_cls.return_value = mock_cleaner
            mock_cleaner.fix_dataset.return_value = (
                mock_dataset,
                {"total_fixed": 0, "total_rows": 1},
            )
            result = runner.invoke(
                main, ["test/dataset", "--dry-run", "--output", "json"]
            )

        assert result.exit_code != 3


# ---------------------------------------------------------------------------
# AC-14-06: 制御文字を含む入力の拒否
# ---------------------------------------------------------------------------


class TestCliControlCharacterRejection:
    """制御文字を含む入力の拒否テスト。"""

    def test_null_char_in_dataset_id_rejected(self) -> None:
        """AC-14-06: DATASET_ID に \\x00 を含む場合、終了コード 1 でエラー終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["test\x00/dataset"])

        assert result.exit_code == 1

    def test_control_char_in_dataset_id_rejected(self) -> None:
        """AC-14-06: DATASET_ID に制御文字（\\x01）を含む場合、終了コード 1 でエラー終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["test\x01/dataset"])

        assert result.exit_code == 1

    def test_control_char_bel_in_dataset_id_rejected(self) -> None:
        """AC-14-06: DATASET_ID に BEL 文字（\\x07）を含む場合、終了コード 1 でエラー終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["test\x07/dataset"])

        assert result.exit_code == 1

    def test_control_char_rejected_before_load(self) -> None:
        """AC-14-06: 制御文字入力の場合、データセット読み込みが開始されない。"""
        from evaldataset.cli import main

        runner = CliRunner()
        with patch("evaldataset.cli.load_hf_dataset") as mock_load:
            result = runner.invoke(main, ["test\x00/dataset"])

        assert result.exit_code == 1
        mock_load.assert_not_called()

    def test_normal_dataset_id_not_rejected(self) -> None:
        """AC-14-06: 正常なデータセットIDは制御文字チェックで拒否されない。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["valid/dataset-name", "--output", "json"])

        # 正常なIDは拒否されない（制御文字起因の終了コード 1 ではない）
        # issue検出なし→0, warning→1, error→2 のいずれか（3は実行エラー）
        assert result.exit_code in (0, 1, 2)

    def test_form_feed_in_dataset_id_rejected(self) -> None:
        """AC-14-06: DATASET_ID に \\x0c (form feed) を含む場合、終了コード 1 でエラー終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["test\x0c/dataset"])

        assert result.exit_code == 1

    def test_tab_in_dataset_id_rejected(self) -> None:
        """AC-14-06: DATASET_ID に \\x0b (vertical tab) を含む場合、終了コード 1 でエラー終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["test\x0b/dataset"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# _run_checkers のベストエフォート実行テスト
# ---------------------------------------------------------------------------


class TestRunCheckersBestEffort:
    """_run_checkers のベストエフォート実行（例外隔離）テスト。"""

    def test_exception_in_checker_produces_error_result(self) -> None:
        """チェッカーが例外を投げた場合、ERROR CheckResultが生成される。"""
        from evaldataset.cli import _run_checkers
        from evaldataset.config import CheckerConfig
        from evaldataset.models import Severity

        dataset = _make_dataset(["text"])
        config = CheckerConfig()

        failing_cls = MagicMock()
        failing_cls.return_value.check.side_effect = RuntimeError("boom")

        with patch("evaldataset.cli.get_all_checkers", return_value={"failing": failing_cls}):
            results = _run_checkers(dataset, "text", config)

        assert len(results) == 1
        result = results[0]
        assert result.checker_name == "failing"
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.ERROR
        assert "boom" in result.issues[0].message

    def test_exception_in_one_checker_does_not_stop_others(self) -> None:
        """チェッカーが例外を投げても残りのチェッカーが続行される。"""
        from evaldataset.cli import _run_checkers
        from evaldataset.config import CheckerConfig

        dataset = _make_dataset(["text"])
        config = CheckerConfig()

        failing_cls = MagicMock()
        failing_cls.return_value.check.side_effect = ValueError("fail")

        ok_result = _make_check_result(checker_name="ok_checker", issues=[])
        ok_cls = MagicMock()
        ok_cls.return_value.check.return_value = ok_result

        checkers = {"failing": failing_cls, "ok_checker": ok_cls}
        with patch("evaldataset.cli.get_all_checkers", return_value=checkers):
            results = _run_checkers(dataset, "text", config)

        # 両方のチェッカーの結果が含まれる
        assert len(results) == 2
        checker_names = [r.checker_name for r in results]
        assert "failing" in checker_names
        assert "ok_checker" in checker_names


# ---------------------------------------------------------------------------
# --skip-checker オプションのテスト
# ---------------------------------------------------------------------------


class TestCliSkipChecker:
    """--skip-checker オプションのテスト。"""

    def test_skip_checker_passed_to_config(self) -> None:
        """--skip-checker で指定したチェッカー名が skip_checkers に渡される。"""
        from evaldataset.cli import main
        from evaldataset.config import CheckerConfig

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config: list[CheckerConfig] = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--skip-checker", "near_duplicate",
                    "--output", "json",
                ],
            )

        assert result.exit_code in (0, 1, 2)
        assert len(captured_config) == 1
        assert "near_duplicate" in captured_config[0].skip_checkers

    def test_multiple_skip_checkers(self) -> None:
        """--skip-checker を複数指定した場合、全て skip_checkers に含まれる。"""
        from evaldataset.cli import main
        from evaldataset.config import CheckerConfig

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config: list[CheckerConfig] = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--skip-checker", "near_duplicate",
                    "--skip-checker", "pii",
                    "--output", "json",
                ],
            )

        assert len(captured_config) == 1
        skip_checkers = captured_config[0].skip_checkers
        assert "near_duplicate" in skip_checkers
        assert "pii" in skip_checkers

    def test_skipped_checker_not_in_results(self) -> None:
        """--skip-checker で指定したチェッカーは results に含まれない。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        mock_near_dup_cls = MagicMock()
        mock_near_dup_cls.return_value.check.return_value = _make_check_result(
            checker_name="near_duplicate"
        )
        mock_near_dup_cls.name = "near_duplicate"

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch(
                 "evaldataset.cli.get_all_checkers",
                 return_value={"near_duplicate": mock_near_dup_cls},
             ):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--skip-checker", "near_duplicate",
                    "--output", "json",
                ],
            )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        checker_names = [r["checker"] for r in parsed["results"]]
        assert "near_duplicate" not in checker_names


# ---------------------------------------------------------------------------
# --config YAMLファイル読み込みのテスト
# ---------------------------------------------------------------------------


class TestCliConfigFile:
    """--config オプションによる YAML 設定ファイル読み込みのテスト。"""

    def test_config_yaml_loaded(self, tmp_path) -> None:
        """--config で指定した YAML ファイルが読み込まれる。"""
        from evaldataset.cli import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("min_length: 100\n")

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--config", str(config_file), "--output", "json"],
            )

        assert result.exit_code in (0, 1, 2)
        assert len(captured_config) == 1
        assert captured_config[0].min_length == 100

    def test_config_yaml_max_length_applied(self, tmp_path) -> None:
        """--config の max_length 設定が正しく反映される。"""
        from evaldataset.cli import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("max_length: 5000\n")

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--config", str(config_file), "--output", "json"],
            )

        assert len(captured_config) == 1
        assert captured_config[0].max_length == 5000

    def test_config_yaml_skip_checkers_applied(self, tmp_path) -> None:
        """--config の skip_checkers 設定が正しく反映される。"""
        from evaldataset.cli import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("skip_checkers:\n  - near_duplicate\n")

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--config", str(config_file), "--output", "json"],
            )

        assert len(captured_config) == 1
        assert "near_duplicate" in captured_config[0].skip_checkers

    def test_config_yaml_with_unknown_keys_no_error(self, tmp_path) -> None:
        """未知のキーを含む YAML ファイルでもエラーにならない。"""
        from evaldataset.cli import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("min_length: 50\nunknown_key: something\n")

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--config", str(config_file), "--output", "json"],
            )

        assert result.exit_code != 3

    def test_cli_overrides_config_file_sample_size(self, tmp_path) -> None:
        """CLI の --sample-size が YAML の設定より優先される。"""
        from evaldataset.cli import main

        config_file = tmp_path / "config.yaml"
        config_file.write_text("sample_size: 50\n")

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_config = []

        def capture_config(dataset_id, split, text_field, config):
            captured_config.append(config)
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_config), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                [
                    "test/dataset",
                    "--config", str(config_file),
                    "--sample-size", "200",
                    "--output", "json",
                ],
            )

        assert len(captured_config) == 1
        # CLI指定の200が優先される
        assert captured_config[0].sample_size == 200


# ---------------------------------------------------------------------------
# --split オプションのテスト
# ---------------------------------------------------------------------------


class TestCliSplitOption:
    """--split オプションのテスト。"""

    def test_default_split_is_train(self) -> None:
        """--split 未指定時はデフォルトで 'train' スプリットが使われる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_calls = []

        def capture_call(dataset_id, split, text_field, config):
            captured_calls.append({"dataset_id": dataset_id, "split": split})
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_call), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert result.exit_code in (0, 1, 2)
        assert captured_calls[0]["split"] == "train"

    def test_custom_split_passed_to_loader(self) -> None:
        """--split で指定したスプリット名がローダーに渡される。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_calls = []

        def capture_call(dataset_id, split, text_field, config):
            captured_calls.append({"dataset_id": dataset_id, "split": split})
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_call), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main, ["test/dataset", "--split", "validation", "--output", "json"]
            )

        assert captured_calls[0]["split"] == "validation"

    def test_split_in_report_output(self) -> None:
        """--split で指定したスプリット名がJSON出力に含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main, ["test/dataset", "--split", "test", "--output", "json"]
            )

        parsed = json.loads(result.output)
        assert parsed["split"] == "test"


# ---------------------------------------------------------------------------
# --text-field オプションのテスト
# ---------------------------------------------------------------------------


class TestCliTextField:
    """--text-field オプションのテスト。"""

    def test_default_text_field_is_text(self) -> None:
        """--text-field 未指定時はデフォルトで 'text' フィールドが使われる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = _make_dataset(["text"])
        captured_calls = []

        def capture_call(dataset_id, split, text_field, config):
            captured_calls.append({"text_field": text_field})
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_call), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(main, ["test/dataset", "--output", "json"])

        assert captured_calls[0]["text_field"] == "text"

    def test_custom_text_field_passed_to_loader(self) -> None:
        """--text-field で指定したフィールド名がローダーに渡される。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = Dataset.from_dict({"content": ["sample content"]})
        captured_calls = []

        def capture_call(dataset_id, split, text_field, config):
            captured_calls.append({"text_field": text_field})
            return mock_dataset

        with patch("evaldataset.cli.load_hf_dataset", side_effect=capture_call), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--text-field", "content", "--output", "json"],
            )

        assert captured_calls[0]["text_field"] == "content"

    def test_text_field_in_report_output(self) -> None:
        """--text-field で指定したフィールド名がJSON出力に含まれる。"""
        from evaldataset.cli import main

        runner = CliRunner()
        mock_dataset = Dataset.from_dict({"body": ["sample text"]})

        with patch("evaldataset.cli.load_hf_dataset", return_value=mock_dataset), \
             patch("evaldataset.cli.get_all_checkers", return_value={}):
            result = runner.invoke(
                main,
                ["test/dataset", "--text-field", "body", "--output", "json"],
            )

        parsed = json.loads(result.output)
        assert parsed["text_field"] == "body"


# ---------------------------------------------------------------------------
# dataset_id 引数の必須チェック
# ---------------------------------------------------------------------------


class TestCliRequiredArgument:
    """dataset_id 引数の必須チェックテスト。"""

    def test_missing_dataset_id_shows_usage_error(self) -> None:
        """DATASET_ID を省略した場合、Clickがエラーを表示する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [])

        # Click の UsageError: 引数不足
        assert result.exit_code != 0

    def test_help_option_works(self) -> None:
        """--help オプションが動作し、終了コード 0 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "DATASET_ID" in result.output

    def test_h_short_help_option_works(self) -> None:
        """-h ショートオプションが動作し、終了コード 0 で終了する。"""
        from evaldataset.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["-h"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 内部ヘルパー関数のユニットテスト
# ---------------------------------------------------------------------------


class TestCliHelpers:
    """cli.py の内部ヘルパー関数のユニットテスト。"""

    def test_validate_dataset_id_returns_none_for_valid_id(self) -> None:
        """_validate_dataset_id: 正常なIDでNoneを返す。"""
        from evaldataset.cli import _validate_dataset_id

        assert _validate_dataset_id("user/dataset") is None
        assert _validate_dataset_id("my-dataset") is None
        assert _validate_dataset_id("user/my-dataset-123") is None

    def test_validate_dataset_id_returns_error_for_null_char(self) -> None:
        """_validate_dataset_id: \\x00 を含むIDでエラーメッセージを返す。"""
        from evaldataset.cli import _validate_dataset_id

        error = _validate_dataset_id("test\x00/dataset")
        assert error is not None
        assert isinstance(error, str)

    def test_validate_dataset_id_returns_error_for_control_char(self) -> None:
        """_validate_dataset_id: 制御文字を含むIDでエラーメッセージを返す。"""
        from evaldataset.cli import _validate_dataset_id

        for char in ["\x01", "\x07", "\x0b", "\x0c", "\x1f"]:
            error = _validate_dataset_id(f"test{char}dataset")
            assert error is not None, f"\\x{ord(char):02x} はエラーを返すべき"

    def test_choose_output_format_json_explicit(self) -> None:
        """_choose_output_format: 'json' が明示された場合は 'json' を返す。"""
        from evaldataset.cli import _choose_output_format

        assert _choose_output_format("json") == "json"

    def test_choose_output_format_rich_when_tty(self) -> None:
        """_choose_output_format: TTY接続時の 'rich' は 'rich' を返す。"""
        from evaldataset.cli import _choose_output_format

        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            result = _choose_output_format("rich")

        assert result == "rich"

    def test_choose_output_format_json_when_not_tty(self) -> None:
        """_choose_output_format: TTY非接続時の 'rich' は 'json' を返す。"""
        from evaldataset.cli import _choose_output_format

        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            result = _choose_output_format("rich")

        assert result == "json"

    def test_exit_code_from_report_no_issues(self) -> None:
        """_exit_code_from_report: Issueなしで EXIT_OK (0) を返す。"""
        from evaldataset.cli import _exit_code_from_report, EXIT_OK

        report = _make_report(results=[])
        assert _exit_code_from_report(report) == EXIT_OK

    def test_exit_code_from_report_warning_only(self) -> None:
        """_exit_code_from_report: WARNINGのみで EXIT_WARNING (1) を返す。"""
        from evaldataset.cli import _exit_code_from_report, EXIT_WARNING

        warning_result = _make_check_result(
            issues=[_make_warning_issue()]
        )
        report = _make_report(results=[warning_result])
        assert _exit_code_from_report(report) == EXIT_WARNING

    def test_exit_code_from_report_error(self) -> None:
        """_exit_code_from_report: ERRORがあれば EXIT_ERROR (2) を返す。"""
        from evaldataset.cli import _exit_code_from_report, EXIT_ERROR

        error_result = _make_check_result(
            issues=[_make_error_issue()]
        )
        report = _make_report(results=[error_result])
        assert _exit_code_from_report(report) == EXIT_ERROR

    def test_exit_code_from_report_error_overrides_warning(self) -> None:
        """_exit_code_from_report: ERRORとWARNINGが混在時は EXIT_ERROR (2) を返す。"""
        from evaldataset.cli import _exit_code_from_report, EXIT_ERROR

        mixed_result = _make_check_result(
            issues=[_make_error_issue(), _make_warning_issue()]
        )
        report = _make_report(results=[mixed_result])
        assert _exit_code_from_report(report) == EXIT_ERROR

    def test_build_config_default_values(self) -> None:
        """_build_config: config_path=None、sample_size=None の場合はデフォルト設定を返す。"""
        from evaldataset.cli import _build_config
        from evaldataset.config import CheckerConfig

        config = _build_config(None, None, [])
        assert isinstance(config, CheckerConfig)
        assert config.sample_size is None
        assert config.skip_checkers == []

    def test_build_config_sample_size_applied(self) -> None:
        """_build_config: sample_size が設定に反映される。"""
        from evaldataset.cli import _build_config

        config = _build_config(None, 100, [])
        assert config.sample_size == 100

    def test_build_config_skip_checkers_merged(self) -> None:
        """_build_config: CLI skip_checkers が設定にマージされる。"""
        from evaldataset.cli import _build_config

        config = _build_config(None, None, ["near_duplicate", "pii"])
        assert "near_duplicate" in config.skip_checkers
        assert "pii" in config.skip_checkers

    def test_build_config_from_yaml(self, tmp_path) -> None:
        """_build_config: YAML ファイルの設定が読み込まれる。"""
        from evaldataset.cli import _build_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("min_length: 200\n")

        config = _build_config(str(config_file), None, [])
        assert config.min_length == 200
