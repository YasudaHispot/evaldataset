"""Rich console reporter for human-readable output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from evaldataset.models import Report, Severity


class RichReporter:
    """Render the quality check report using Rich tables and panels.

    Used as the default reporter when stdout is a TTY and ``--output json``
    is not specified.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def render(self, report: Report, fix_stats: dict[str, Any] | None = None) -> None:
        """Print the report to the console using Rich formatting.

        Parameters
        ----------
        report:
            The aggregated quality check report.
        fix_stats:
            Optional statistics from the TextCleaner fix pipeline.
        """
        self._render_header(report)
        self._render_results_table(report)
        self._render_issues_detail(report)
        if fix_stats is not None:
            self._render_fix_stats(fix_stats)
        self._render_summary(report)

    def render_error(self, message: str) -> None:
        """Print an error message to stderr via Rich console.

        Parameters
        ----------
        message:
            The error description to display.
        """
        err_console = Console(stderr=True)
        err_console.print(f"[bold red]Error:[/bold red] {message}")

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    def _render_header(self, report: Report) -> None:
        """Render the dataset info header panel."""
        header_text = (
            f"Dataset: [bold]{report.dataset_id}[/bold]\n"
            f"Split: {report.split} | "
            f"Rows: {report.total_rows:,} | "
            f"Text field: {report.text_field}"
        )
        self._console.print(Panel(header_text, title="Dataset Quality Report"))

    def _render_results_table(self, report: Report) -> None:
        """Render the checker results summary table."""
        table = Table(title="Checker Results")
        table.add_column("Checker", style="cyan", no_wrap=True)
        table.add_column("Issues", justify="right")
        table.add_column("Errors", justify="right", style="red")
        table.add_column("Warnings", justify="right", style="yellow")
        table.add_column("Status", justify="center")

        for result in report.results:
            issue_count = len(result.issues)
            if result.error_count > 0:
                status = Text("FAIL", style="bold red")
            elif result.warning_count > 0:
                status = Text("WARN", style="bold yellow")
            else:
                status = Text("PASS", style="bold green")

            table.add_row(
                result.checker_name,
                str(issue_count),
                str(result.error_count),
                str(result.warning_count),
                status,
            )

        self._console.print(table)

    def _render_issues_detail(self, report: Report) -> None:
        """Render detailed issue information for each checker with issues."""
        for result in report.results:
            if not result.has_issues:
                continue

            for issue in result.issues:
                severity_style = _severity_style(issue.severity)
                affected = len(issue.row_indices)
                sample = issue.row_indices[:10]

                self._console.print(
                    f"\n[{severity_style}][{issue.severity.value.upper()}][/{severity_style}] "
                    f"[bold]{issue.checker}[/bold]: {issue.message}"
                )
                if affected > 0:
                    self._console.print(
                        f"  Affected rows: {affected:,}"
                        + (f" (sample: {sample})" if sample else "")
                    )
                if issue.details:
                    for key, value in issue.details.items():
                        self._console.print(f"  {key}: {value}")

    def _render_fix_stats(self, fix_stats: dict[str, Any]) -> None:
        """Render fix pipeline statistics."""
        table = Table(title="Fix Statistics")
        table.add_column("Step", style="cyan")
        table.add_column("Rows Fixed", justify="right")

        for key, value in fix_stats.items():
            if key != "total_rows" and isinstance(value, int):
                table.add_row(key, str(value))

        self._console.print(table)

    def _render_summary(self, report: Report) -> None:
        """Render the final summary panel."""
        if report.total_errors > 0:
            style = "red"
            verdict = "ERRORS FOUND"
        elif report.total_warnings > 0:
            style = "yellow"
            verdict = "WARNINGS FOUND"
        else:
            style = "green"
            verdict = "ALL CHECKS PASSED"

        summary_text = (
            f"Total issues: {report.total_issues} | "
            f"Errors: {report.total_errors} | "
            f"Warnings: {report.total_warnings}"
        )
        self._console.print(
            Panel(summary_text, title=f"[bold {style}]{verdict}[/bold {style}]")
        )


def _severity_style(severity: Severity) -> str:
    """Return the Rich style string for a given severity level."""
    if severity == Severity.ERROR:
        return "bold red"
    if severity == Severity.WARNING:
        return "bold yellow"
    return "bold blue"
