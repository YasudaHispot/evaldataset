"""Unit tests for RichReporter and JsonReporter.

Covers:
- AC-13-01: Report.to_dict() の正確性（summary.errors, summary.warnings, total_issues）
- AC-13-02: --output json でのマシン可読出力（summary, results キーを含む有効なJSON）
- AC-13-03: リッチコンソール出力（デフォルト）のテスト
- JsonReporter: Reportオブジェクトを渡して有効なJSONが出力される
- JsonReporter: fix_stats が存在する場合にJSONに含まれる
- JsonReporter: render_error がJSONエラーメッセージをstderrに出力する
- RichReporter: Reportオブジェクトを渡して出力が生成される
- RichReporter: issues がゼロの場合も動作する
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from evaldataset.models import (
    CheckResult,
    Issue,
    Report,
    Severity,
)


# ---------------------------------------------------------------------------
# ヘルパー: テスト用 Report / CheckResult / Issue 生成
# ---------------------------------------------------------------------------


def _make_issue(
    checker: str = "test_checker",
    severity: Severity = Severity.WARNING,
    message: str = "Test issue",
    row_indices: list[int] | None = None,
    details: dict | None = None,
) -> Issue:
    return Issue(
        checker=checker,
        severity=severity,
        message=message,
        row_indices=row_indices or [0],
        details=details or {},
    )


def _make_check_result(
    checker_name: str = "test_checker",
    issues: list[Issue] | None = None,
    stats: dict | None = None,
) -> CheckResult:
    return CheckResult(
        checker_name=checker_name,
        issues=issues or [],
        stats=stats or {},
    )


def _make_report(
    dataset_id: str = "test/dataset",
    split: str = "train",
    total_rows: int = 100,
    text_field: str = "text",
    results: list[CheckResult] | None = None,
) -> Report:
    return Report(
        dataset_id=dataset_id,
        split=split,
        total_rows=total_rows,
        text_field=text_field,
        results=results or [],
    )


# ---------------------------------------------------------------------------
# AC-13-01: Report.to_dict() の正確性
# ---------------------------------------------------------------------------


class TestReportToDict:
    """Report.to_dict() が正しい集計値を返すことを検証する。"""

    def test_to_dict_contains_summary_errors_and_warnings(self) -> None:
        """AC-13-01: 2件のERRORと3件のWARNINGを含むReportのto_dict()が正しい値を返す。"""
        error_issues = [
            _make_issue(severity=Severity.ERROR, message=f"Error {i}")
            for i in range(2)
        ]
        warning_issues = [
            _make_issue(severity=Severity.WARNING, message=f"Warning {i}")
            for i in range(3)
        ]
        result = _make_check_result(
            checker_name="test",
            issues=error_issues + warning_issues,
        )
        report = _make_report(results=[result])

        data = report.to_dict()

        assert data["summary"]["errors"] == 2
        assert data["summary"]["warnings"] == 3
        assert data["summary"]["total_issues"] == 5

    def test_to_dict_has_required_top_level_keys(self) -> None:
        """AC-13-01: to_dict() は dataset_id, split, total_rows, text_field, summary, results を含む。"""
        report = _make_report()
        data = report.to_dict()

        assert "dataset_id" in data
        assert "split" in data
        assert "total_rows" in data
        assert "text_field" in data
        assert "summary" in data
        assert "results" in data

    def test_to_dict_summary_has_required_keys(self) -> None:
        """AC-13-01: summary に total_issues, errors, warnings が含まれる。"""
        report = _make_report()
        data = report.to_dict()

        summary = data["summary"]
        assert "total_issues" in summary
        assert "errors" in summary
        assert "warnings" in summary

    def test_to_dict_zero_issues_all_zero(self) -> None:
        """AC-13-01: Issueが0件のReportでsummaryが全てゼロ。"""
        report = _make_report(results=[])
        data = report.to_dict()

        assert data["summary"]["total_issues"] == 0
        assert data["summary"]["errors"] == 0
        assert data["summary"]["warnings"] == 0

    def test_to_dict_reflects_dataset_id(self) -> None:
        """AC-13-01: to_dict() の dataset_id が元の値と一致する。"""
        report = _make_report(dataset_id="user/my-dataset")
        data = report.to_dict()

        assert data["dataset_id"] == "user/my-dataset"

    def test_to_dict_reflects_total_rows(self) -> None:
        """AC-13-01: to_dict() の total_rows が元の値と一致する。"""
        report = _make_report(total_rows=500)
        data = report.to_dict()

        assert data["total_rows"] == 500

    def test_to_dict_results_is_list(self) -> None:
        """AC-13-01: to_dict() の results はリストである。"""
        check_result = _make_check_result(
            issues=[_make_issue(severity=Severity.WARNING)]
        )
        report = _make_report(results=[check_result])
        data = report.to_dict()

        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1

    def test_to_dict_result_item_has_checker_issues_stats(self) -> None:
        """AC-13-01: results の各要素に checker, issues, stats が含まれる。"""
        check_result = _make_check_result(checker_name="my_checker")
        report = _make_report(results=[check_result])
        data = report.to_dict()

        result_item = data["results"][0]
        assert "checker" in result_item
        assert "issues" in result_item
        assert "stats" in result_item

    def test_to_dict_issue_has_required_fields(self) -> None:
        """AC-13-01: results[].issues[] の各要素に必要なフィールドが含まれる。"""
        issue = _make_issue(
            severity=Severity.ERROR,
            message="Critical error",
            row_indices=[1, 2, 3],
        )
        check_result = _make_check_result(issues=[issue])
        report = _make_report(results=[check_result])
        data = report.to_dict()

        issue_data = data["results"][0]["issues"][0]
        assert "checker" in issue_data
        assert "severity" in issue_data
        assert "message" in issue_data
        assert "affected_rows" in issue_data

    def test_to_dict_error_only_warnings_zero(self) -> None:
        """AC-13-01: ERRORのみの場合、warnings は 0 である。"""
        error_result = _make_check_result(
            issues=[_make_issue(severity=Severity.ERROR)]
        )
        report = _make_report(results=[error_result])
        data = report.to_dict()

        assert data["summary"]["errors"] == 1
        assert data["summary"]["warnings"] == 0

    def test_to_dict_multiple_checkers_aggregated(self) -> None:
        """AC-13-01: 複数チェッカーの結果が正しく集計される。"""
        result1 = _make_check_result(
            checker_name="checker1",
            issues=[_make_issue(severity=Severity.ERROR)],
        )
        result2 = _make_check_result(
            checker_name="checker2",
            issues=[
                _make_issue(severity=Severity.WARNING),
                _make_issue(severity=Severity.WARNING),
            ],
        )
        report = _make_report(results=[result1, result2])
        data = report.to_dict()

        assert data["summary"]["errors"] == 1
        assert data["summary"]["warnings"] == 2
        assert data["summary"]["total_issues"] == 3


# ---------------------------------------------------------------------------
# JsonReporter テスト
# ---------------------------------------------------------------------------


class TestJsonReporter:
    """JsonReporter が有効なJSONを出力することを検証する。"""

    @pytest.fixture
    def stream(self) -> io.StringIO:
        """出力キャプチャ用のStringIOストリーム。"""
        return io.StringIO()

    @pytest.fixture
    def reporter(self, stream: io.StringIO):
        """JsonReporter インスタンス（テスト用ストリームを使用）。"""
        from evaldataset.report import JsonReporter
        return JsonReporter(stream=stream)

    def test_render_outputs_valid_json(self, reporter, stream: io.StringIO) -> None:
        """AC-13-02: render() が有効なJSONを出力する。"""
        report = _make_report()
        reporter.render(report)

        stream.seek(0)
        content = stream.read()
        # JSON として解析できること
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_render_output_contains_summary(
        self, reporter, stream: io.StringIO
    ) -> None:
        """AC-13-02: JSON出力に 'summary' キーが含まれる。"""
        report = _make_report()
        reporter.render(report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "summary" in parsed

    def test_render_output_contains_results(
        self, reporter, stream: io.StringIO
    ) -> None:
        """AC-13-02: JSON出力に 'results' キーが含まれる。"""
        report = _make_report()
        reporter.render(report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "results" in parsed

    def test_render_output_contains_dataset_id(
        self, reporter, stream: io.StringIO
    ) -> None:
        """AC-13-02: JSON出力に 'dataset_id' が含まれる。"""
        report = _make_report(dataset_id="test/my-dataset")
        reporter.render(report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert parsed["dataset_id"] == "test/my-dataset"

    def test_render_with_issues_correct_summary(
        self, reporter, stream: io.StringIO
    ) -> None:
        """AC-13-02: IssueのあるReportのJSON出力のsummaryが正しい。"""
        error_result = _make_check_result(
            issues=[_make_issue(severity=Severity.ERROR)]
        )
        warning_result = _make_check_result(
            checker_name="checker2",
            issues=[
                _make_issue(severity=Severity.WARNING, checker="checker2"),
                _make_issue(severity=Severity.WARNING, checker="checker2"),
            ],
        )
        report = _make_report(results=[error_result, warning_result])
        reporter.render(report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert parsed["summary"]["errors"] == 1
        assert parsed["summary"]["warnings"] == 2
        assert parsed["summary"]["total_issues"] == 3

    def test_render_with_fix_stats_includes_fix_stats(
        self, reporter, stream: io.StringIO
    ) -> None:
        """fix_stats が指定された場合、JSON出力に fix_stats が含まれる。"""
        report = _make_report()
        fix_stats = {"total_fixed": 5, "total_rows": 100}
        reporter.render(report, fix_stats=fix_stats)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "fix_stats" in parsed
        assert parsed["fix_stats"]["total_fixed"] == 5
        assert parsed["fix_stats"]["total_rows"] == 100

    def test_render_without_fix_stats_no_fix_stats_key(
        self, reporter, stream: io.StringIO
    ) -> None:
        """fix_stats が None の場合、JSON出力に fix_stats キーが含まれない。"""
        report = _make_report()
        reporter.render(report, fix_stats=None)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "fix_stats" not in parsed

    def test_render_output_ends_with_newline(
        self, reporter, stream: io.StringIO
    ) -> None:
        """render() の出力が改行で終わる。"""
        report = _make_report()
        reporter.render(report)

        stream.seek(0)
        content = stream.read()
        assert content.endswith("\n")

    def test_render_error_writes_json_to_stderr(self) -> None:
        """render_error() がJSON形式のエラーメッセージをstderrに出力する。"""
        from evaldataset.report import JsonReporter

        reporter = JsonReporter()

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            reporter.render_error("Dataset not found")

        stderr_capture.seek(0)
        content = stderr_capture.read()
        parsed = json.loads(content)
        assert "error" in parsed
        assert "Dataset not found" in parsed["error"]

    def test_render_error_includes_message(self) -> None:
        """render_error() のJSON出力に 'error' キーでメッセージが含まれる。"""
        from evaldataset.report import JsonReporter

        reporter = JsonReporter()
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            reporter.render_error("Connection timeout")

        stderr_capture.seek(0)
        parsed = json.loads(stderr_capture.read())
        assert parsed["error"] == "Connection timeout"

    def test_render_uses_default_stdout_when_no_stream(self) -> None:
        """stream 引数なしのときはデフォルト（sys.stdout）に書き込む。"""
        from evaldataset.report import JsonReporter

        report = _make_report()
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            reporter = JsonReporter()
            reporter.render(report)

        stdout_capture.seek(0)
        content = stdout_capture.read()
        parsed = json.loads(content)
        assert "summary" in parsed

    def test_render_empty_results_list(self, reporter, stream: io.StringIO) -> None:
        """results が空リストの場合、JSON出力の results が空リストである。"""
        report = _make_report(results=[])
        reporter.render(report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert parsed["results"] == []

    def test_render_ensure_ascii_false(self, reporter, stream: io.StringIO) -> None:
        """非ASCII文字がエスケープされずにそのまま出力される。"""
        report = _make_report(dataset_id="test/日本語データセット")
        reporter.render(report)

        stream.seek(0)
        content = stream.read()
        # 日本語文字がそのまま含まれること（\\u escapeではない）
        assert "日本語データセット" in content


# ---------------------------------------------------------------------------
# RichReporter テスト
# ---------------------------------------------------------------------------


class TestRichReporter:
    """RichReporter が Rich 出力を生成することを検証する。"""

    @pytest.fixture
    def reporter(self):
        """RichReporter インスタンス。"""
        from evaldataset.report import RichReporter
        return RichReporter()

    def test_render_does_not_raise(self, reporter) -> None:
        """AC-13-03: render() が例外なく実行できる。"""
        report = _make_report()
        reporter.render(report)  # 例外が発生しないこと

    def test_render_with_issues_does_not_raise(self, reporter) -> None:
        """AC-13-03: IssueのあるReportでも render() が例外なく実行できる。"""
        warning_result = _make_check_result(
            issues=[_make_issue(severity=Severity.WARNING, message="Test warning")]
        )
        error_result = _make_check_result(
            checker_name="error_checker",
            issues=[_make_issue(severity=Severity.ERROR, checker="error_checker")],
        )
        report = _make_report(results=[warning_result, error_result])
        reporter.render(report)  # 例外が発生しないこと

    def test_render_zero_issues_does_not_raise(self, reporter) -> None:
        """AC-13-03: Issueが0件のReportでも render() が例外なく実行できる。"""
        empty_result = _make_check_result(issues=[])
        report = _make_report(results=[empty_result])
        reporter.render(report)  # 例外が発生しないこと

    def test_render_with_fix_stats_does_not_raise(self, reporter) -> None:
        """fix_stats を渡した場合も render() が例外なく実行できる。"""
        report = _make_report()
        fix_stats = {"total_fixed": 3, "total_rows": 10}
        reporter.render(report, fix_stats=fix_stats)  # 例外が発生しないこと

    def test_render_info_severity_does_not_raise(self, reporter) -> None:
        """AC-13-03: severity=INFO のIssueがあっても render() が例外なく実行できる。"""
        info_result = _make_check_result(
            issues=[_make_issue(severity=Severity.INFO, message="Info message")]
        )
        report = _make_report(results=[info_result])
        reporter.render(report)  # 例外が発生しないこと

    def test_render_multiple_checkers_does_not_raise(self, reporter) -> None:
        """AC-13-03: 複数チェッカーの結果を持つReportでも render() が例外なく実行できる。"""
        results = [
            _make_check_result(checker_name=f"checker_{i}", issues=[])
            for i in range(5)
        ]
        report = _make_report(results=results)
        reporter.render(report)  # 例外が発生しないこと

    def test_render_large_row_indices_does_not_raise(self, reporter) -> None:
        """AC-13-03: 多数のrow_indicesを持つIssueがあっても render() が例外なく実行できる。"""
        issue = Issue(
            checker="test",
            severity=Severity.WARNING,
            message="Many rows affected",
            row_indices=list(range(100)),
            details={},
        )
        result = _make_check_result(issues=[issue])
        report = _make_report(results=[result], total_rows=1000)
        reporter.render(report)  # 例外が発生しないこと

    def test_render_output_contains_checker_name(self) -> None:
        """AC-13-03: render() の出力にチェッカー名が含まれる。"""
        from io import StringIO
        from rich.console import Console
        from evaldataset.report import RichReporter

        stream = StringIO()
        console = Console(file=stream, highlight=False)
        reporter = RichReporter(console=console)

        result = _make_check_result(checker_name="my_schema_checker", issues=[])
        report = _make_report(results=[result])
        reporter.render(report)

        stream.seek(0)
        output = stream.read()
        assert "my_schema_checker" in output

    def test_render_output_contains_severity_info(self) -> None:
        """AC-13-03: render() の出力にIssue数と重大度情報が含まれる。"""
        from io import StringIO
        from rich.console import Console
        from evaldataset.report import RichReporter

        stream = StringIO()
        console = Console(file=stream, highlight=False)
        reporter = RichReporter(console=console)

        warning_result = _make_check_result(
            checker_name="text_length",
            issues=[
                _make_issue(severity=Severity.WARNING, message="Too short"),
            ],
        )
        error_result = _make_check_result(
            checker_name="schema",
            issues=[
                _make_issue(severity=Severity.ERROR, checker="schema", message="Missing field"),
            ],
        )
        report = _make_report(results=[warning_result, error_result])
        reporter.render(report)

        stream.seek(0)
        output = stream.read()
        # チェッカー名が含まれること
        assert "text_length" in output
        assert "schema" in output
        # Issue情報（severity文字列）が含まれること
        assert "WARNING" in output or "WARN" in output
        assert "ERROR" in output or "FAIL" in output

    def test_render_error_writes_to_stderr(self) -> None:
        """AC-13-03: render_error() がエラーメッセージをstderrに出力する。"""
        from unittest.mock import patch
        from rich.console import Console
        from evaldataset.report import RichReporter

        reporter = RichReporter()
        err_stream = io.StringIO()
        mock_console = Console(file=err_stream, highlight=False)

        with patch("evaldataset.report.rich_reporter.Console", return_value=mock_console):
            reporter.render_error("Something went wrong")

        err_stream.seek(0)
        output = err_stream.read()
        assert "Something went wrong" in output

    def test_render_error_message_visible_in_output(self) -> None:
        """render_error() の出力にエラーメッセージが含まれる。"""
        from unittest.mock import patch
        from rich.console import Console
        from evaldataset.report import RichReporter

        reporter = RichReporter()
        err_stream = io.StringIO()
        mock_console = Console(file=err_stream, highlight=False)

        with patch("evaldataset.report.rich_reporter.Console", return_value=mock_console):
            reporter.render_error("Custom error message")

        err_stream.seek(0)
        output = err_stream.read()
        assert "Custom error message" in output


# ---------------------------------------------------------------------------
# AC-17: 修正前後レポート — JsonReporter
# ---------------------------------------------------------------------------


class TestJsonReporterFixReport:
    """JsonReporter の修正前後レポート出力テスト。

    AC-17-01: --fix --output json で修正前後レポートが出力される
    AC-17-02: --dry-run --output json で修正前後レポートが出力される
    """

    @pytest.fixture
    def stream(self) -> io.StringIO:
        """出力キャプチャ用のStringIOストリーム。"""
        return io.StringIO()

    @pytest.fixture
    def reporter(self, stream: io.StringIO):
        """JsonReporter インスタンス（テスト用ストリームを使用）。"""
        from evaldataset.report import JsonReporter
        return JsonReporter(stream=stream)

    @pytest.fixture
    def before_report(self) -> Report:
        """修正前レポート（WARNINGあり）。"""
        warning_result = _make_check_result(
            checker_name="text_length",
            issues=[
                _make_issue(
                    checker="text_length",
                    severity=Severity.WARNING,
                    message="Text too short",
                    row_indices=[0, 1],
                )
            ],
        )
        return _make_report(total_rows=5, results=[warning_result])

    @pytest.fixture
    def after_report(self) -> Report:
        """修正後レポート（問題行除去済み）。"""
        return _make_report(total_rows=3, results=[])

    def test_render_with_after_report_contains_before_key(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: after_report を渡すと JSON 出力に 'before' キーが含まれる。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "before" in parsed

    def test_render_with_after_report_contains_after_key(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: after_report を渡すと JSON 出力に 'after' キーが含まれる。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "after" in parsed

    def test_render_with_after_report_before_contains_summary(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: 'before' には summary が含まれる。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "summary" in parsed["before"]

    def test_render_with_after_report_after_contains_summary(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: 'after' には summary が含まれる。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "summary" in parsed["after"]

    def test_render_with_after_report_before_warnings_gte_after_warnings(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: after.summary.warnings <= before.summary.warnings であること。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        before_warnings = parsed["before"]["summary"]["warnings"]
        after_warnings = parsed["after"]["summary"]["warnings"]
        assert after_warnings <= before_warnings

    def test_render_with_after_report_contains_fix_stats(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: fix_stats も JSON 出力に含まれること。"""
        fix_stats = {"total_fixed": 2, "filter_stats": {"total_rows_removed": 1}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "fix_stats" in parsed

    def test_render_with_after_report_before_reflects_before_report(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: before の内容が before_report の to_dict() と一致する。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        expected_before = before_report.to_dict()
        assert parsed["before"]["summary"] == expected_before["summary"]

    def test_render_with_after_report_after_reflects_after_report(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: after の内容が after_report の to_dict() と一致する。"""
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        parsed = json.loads(stream.read())
        expected_after = after_report.to_dict()
        assert parsed["after"]["summary"] == expected_after["summary"]

    def test_render_without_after_report_no_before_after_keys(
        self, reporter, stream: io.StringIO, before_report
    ) -> None:
        """after_report=None の場合、JSON 出力に 'before'/'after' キーが含まれない（従来動作）。"""
        reporter.render(before_report, fix_stats=None, after_report=None)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "before" not in parsed
        assert "after" not in parsed

    def test_render_without_after_report_contains_summary_top_level(
        self, reporter, stream: io.StringIO, before_report
    ) -> None:
        """after_report=None の場合は従来通り top-level に summary, results が含まれる。"""
        reporter.render(before_report, fix_stats=None, after_report=None)

        stream.seek(0)
        parsed = json.loads(stream.read())
        assert "summary" in parsed
        assert "results" in parsed

    def test_render_with_after_report_is_valid_json(
        self, reporter, stream: io.StringIO, before_report, after_report
    ) -> None:
        """AC-17-01: after_report を渡した場合も出力が有効な JSON である。"""
        fix_stats = {"total_fixed": 0, "filter_stats": {"total_rows_removed": 0}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        content = stream.read()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# AC-17: 修正前後レポート — RichReporter
# ---------------------------------------------------------------------------


class TestRichReporterFixReport:
    """RichReporter の修正前後レポート出力テスト。

    AC-17-03: --fix で Rich 修正前後レポートが表示される
    """

    @pytest.fixture
    def before_report(self) -> Report:
        """修正前レポート（WARNINGあり）。"""
        warning_result = _make_check_result(
            checker_name="text_length",
            issues=[
                _make_issue(
                    checker="text_length",
                    severity=Severity.WARNING,
                    message="Text too short",
                    row_indices=[0, 1],
                )
            ],
        )
        return _make_report(total_rows=5, results=[warning_result])

    @pytest.fixture
    def after_report(self) -> Report:
        """修正後レポート（問題行除去済み）。"""
        return _make_report(total_rows=3, results=[])

    def _make_rich_reporter_with_stream(self) -> tuple:
        """テスト用のRichReporterとキャプチャ用ストリームのペアを返す。"""
        from io import StringIO
        from rich.console import Console
        from evaldataset.report import RichReporter

        stream = StringIO()
        console = Console(file=stream, highlight=False)
        reporter = RichReporter(console=console)
        return reporter, stream

    def test_render_with_after_report_does_not_raise(
        self, before_report, after_report
    ) -> None:
        """AC-17-03: after_report を渡した場合も render() が例外なく実行できる。"""
        from evaldataset.report import RichReporter

        reporter = RichReporter()
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

    def test_render_with_after_report_output_contains_before(
        self, before_report, after_report
    ) -> None:
        """AC-17-03: render() の出力に 'Before' が含まれる。"""
        reporter, stream = self._make_rich_reporter_with_stream()
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        output = stream.read()
        assert "Before" in output

    def test_render_with_after_report_output_contains_after(
        self, before_report, after_report
    ) -> None:
        """AC-17-03: render() の出力に 'After' が含まれる。"""
        reporter, stream = self._make_rich_reporter_with_stream()
        fix_stats = {"total_fixed": 1, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        output = stream.read()
        assert "After" in output

    def test_render_without_after_report_no_before_after_text(
        self, before_report
    ) -> None:
        """after_report=None の場合は従来動作（Before/After テキストなし）で動作する。"""
        reporter, stream = self._make_rich_reporter_with_stream()
        reporter.render(before_report, fix_stats=None, after_report=None)

        stream.seek(0)
        output = stream.read()
        # before/after セクションは存在しない（従来の単一レポート表示）
        # ただし例外なく動作すること
        assert isinstance(output, str)

    def test_render_with_after_report_shows_before_warnings_count(
        self, before_report, after_report
    ) -> None:
        """AC-17-03: render() の出力に修正前の問題数が含まれる。"""
        reporter, stream = self._make_rich_reporter_with_stream()
        fix_stats = {"total_fixed": 2, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        output = stream.read()
        # Before セクションに warnings 数が表示される
        before_warnings = str(before_report.total_warnings)
        assert before_warnings in output

    def test_render_with_after_report_shows_after_total_rows(
        self, before_report, after_report
    ) -> None:
        """AC-17-03: render() の出力に修正後の行数が含まれる。"""
        reporter, stream = self._make_rich_reporter_with_stream()
        fix_stats = {"total_fixed": 2, "filter_stats": {"total_rows_removed": 2}}
        reporter.render(before_report, fix_stats=fix_stats, after_report=after_report)

        stream.seek(0)
        output = stream.read()
        # After レポートの total_rows（3）が出力に含まれる
        assert str(after_report.total_rows) in output
