"""CLI entry point for the evaldataset quality checker.

Usage::

    evaldataset <DATASET_ID> [OPTIONS]

See ``evaldataset --help`` for full option list.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

import click

from evaldataset.checks import get_all_checkers
from evaldataset.config import CheckerConfig
from evaldataset.fixer import RowFilter, TextCleaner
from evaldataset.loader import load_hf_dataset
from evaldataset.models import CheckResult, Issue, Report, Severity
from evaldataset.report.json_reporter import JsonReporter
from evaldataset.report.rich_reporter import RichReporter

logger = logging.getLogger(__name__)

# Exit codes ----------------------------------------------------------

EXIT_OK = 0
EXIT_WARNING = 1
EXIT_ERROR = 2
EXIT_RUNTIME_ERROR = 3

# Input validation ----------------------------------------------------

# Matches C0/C1 control characters except common whitespace (\t \n \r \x20).
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


def _validate_dataset_id(dataset_id: str) -> str | None:
    """Return an error message if *dataset_id* contains control characters."""
    if _CONTROL_CHAR_RE.search(dataset_id):
        return (
            "DATASET_ID contains control characters. "
            "Only printable characters are allowed."
        )
    return None


# Reporter selection ---------------------------------------------------


def _choose_output_format(explicit: str) -> str:
    """Decide the output format considering TTY detection.

    If the caller passed ``--output json``, honour it.  If ``--output``
    was left at the default (``rich``) **and** stdout is not a TTY, fall
    back to ``json`` automatically (AC-14-03b).
    """
    if explicit == "json":
        return "json"
    if explicit == "rich" and not sys.stdout.isatty():
        return "json"
    return explicit


# Checker pipeline -----------------------------------------------------


def _run_checkers(
    dataset: Any,
    text_field: str,
    config: CheckerConfig,
) -> list[CheckResult]:
    """Execute all registered checkers in best-effort mode.

    If a single checker raises an exception the error is captured as an
    ``ERROR``-level ``CheckResult`` and the remaining checkers continue.

    Special logic:
    * If ``SchemaChecker`` reports a text-field-missing ERROR, subsequent
      text-based checkers are skipped (they would all fail on the missing
      column anyway).
    """
    all_checkers = get_all_checkers()
    results: list[CheckResult] = []
    skip_text_checkers = False

    for name, checker_cls in all_checkers.items():
        # Honour --skip-checker / config.skip_checkers
        if name in config.skip_checkers:
            continue

        # If SchemaChecker reported text-field ERROR, skip text-based
        # checkers (everything except schema itself).
        if skip_text_checkers and name != "schema":
            continue

        try:
            checker = checker_cls(config)
            result = checker.check(dataset, text_field)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Checker '%s' raised %s: %s", name, type(exc).__name__, exc)
            result = CheckResult(
                checker_name=name,
                issues=[
                    Issue(
                        checker=name,
                        severity=Severity.ERROR,
                        message=f"Checker raised an exception: {exc}",
                    )
                ],
            )

        results.append(result)

        # After SchemaChecker, inspect for field-missing ERROR
        if name == "schema" and result.error_count > 0:
            skip_text_checkers = True

    return results


# CLI command ----------------------------------------------------------


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("dataset_id")
@click.option("--split", default="train", show_default=True, help="Target split.")
@click.option(
    "--text-field", default="text", show_default=True, help="Text column name."
)
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="YAML config file path.",
)
@click.option(
    "--output",
    "output_format",
    default="rich",
    show_default=True,
    type=click.Choice(["rich", "json"]),
    help="Output format.",
)
@click.option("--fix", is_flag=True, default=False, help="Run auto-fix pipeline.")
@click.option(
    "--fix-output", default=None, help="Output path for fixed dataset."
)
@click.option(
    "--sample-size",
    default=None,
    type=int,
    help="Number of rows to sample.",
)
@click.option(
    "--skip-checker",
    multiple=True,
    help="Checker name to skip (repeatable).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show fix targets without writing.",
)
def main(
    dataset_id: str,
    split: str,
    text_field: str,
    config_path: str | None,
    output_format: str,
    fix: bool,
    fix_output: str | None,
    sample_size: int | None,
    skip_checker: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Check quality of a HuggingFace dataset.

    DATASET_ID is the HuggingFace Hub dataset identifier
    (e.g. "username/dataset-name").
    """
    # --- Resolve output format (TTY auto-detection) ---
    resolved_format = _choose_output_format(output_format)
    is_json = resolved_format == "json"

    # --- Input validation: reject control characters (AC-14-06) ---
    validation_error = _validate_dataset_id(dataset_id)
    if validation_error is not None:
        _emit_error(validation_error, is_json)
        raise SystemExit(EXIT_WARNING)

    # --- Build config (merge YAML + CLI options) ---
    try:
        config = _build_config(config_path, sample_size, list(skip_checker))
    except Exception as exc:  # noqa: BLE001
        _emit_error(str(exc), is_json)
        raise SystemExit(EXIT_RUNTIME_ERROR) from exc

    # --- Load dataset ---
    try:
        dataset = load_hf_dataset(
            dataset_id, split=split, text_field=text_field, config=config
        )
    except Exception as exc:  # noqa: BLE001
        _emit_error(
            f"Failed to load dataset '{dataset_id}': {exc}",
            is_json,
        )
        raise SystemExit(EXIT_RUNTIME_ERROR) from exc

    # --- Run checker pipeline ---
    results = _run_checkers(dataset, text_field, config)

    # --- Build report ---
    report = Report(
        dataset_id=dataset_id,
        split=split,
        total_rows=len(dataset),
        text_field=text_field,
        results=results,
    )

    # --- Fix pipeline (optional) ---
    fix_stats: dict[str, Any] | None = None
    if fix or dry_run:
        fix_stats = _run_fix_pipeline(
            dataset, text_field, config, fix_output, dry_run, is_json
        )

    # --- Render report ---
    if is_json:
        JsonReporter().render(report, fix_stats=fix_stats)
    else:
        RichReporter().render(report, fix_stats=fix_stats)

    # --- Determine exit code ---
    exit_code = _exit_code_from_report(report)
    raise SystemExit(exit_code)


# Helpers --------------------------------------------------------------


def _build_config(
    config_path: str | None,
    sample_size: int | None,
    skip_checkers: list[str],
) -> CheckerConfig:
    """Merge YAML config with CLI overrides."""
    if config_path:
        config = CheckerConfig.from_yaml(config_path)
    else:
        config = CheckerConfig()

    # CLI overrides take precedence
    if sample_size is not None:
        config.sample_size = sample_size
    if skip_checkers:
        # Merge: YAML skip_checkers + CLI --skip-checker
        existing = set(config.skip_checkers)
        existing.update(skip_checkers)
        config.skip_checkers = sorted(existing)

    return config


def _run_fix_pipeline(
    dataset: Any,
    text_field: str,
    config: CheckerConfig,
    fix_output: str | None,
    dry_run: bool,
    is_json: bool,
) -> dict[str, Any]:
    """Run the full fix pipeline: TextCleaner -> checkers -> RowFilter.

    Pipeline steps:
    1. TextCleaner: text-level transformations (mojibake, HTML, control
       chars, whitespace).
    2. Re-run checkers on the cleaned dataset to get fresh results.
    3. RowFilter: remove problem rows based on checker results.

    In ``--dry-run`` mode the pipeline reports what would change but does
    not write the output.
    """
    # Step 1: TextCleaner (text transformations)
    cleaner = TextCleaner()
    cleaned_dataset, clean_stats = cleaner.fix_dataset(dataset, text_field)

    # Step 2: Run checkers on cleaned data to get fresh results
    check_results = _run_checkers(cleaned_dataset, text_field, config)

    # Step 3: Preprocess duplicate results (keep first of each group)
    # then run RowFilter to remove problem rows
    row_filter = RowFilter()
    adjusted_results = row_filter.strip_first_duplicates(
        cleaned_dataset, check_results, text_field=text_field
    )
    filtered_dataset, filter_stats = row_filter.filter_dataset(
        cleaned_dataset,
        adjusted_results,
        skip_checkers=config.skip_checkers,
    )

    # Merge clean_stats and filter_stats into a combined stats dict
    stats: dict[str, Any] = {**clean_stats, "filter_stats": filter_stats}

    if dry_run:
        # In dry-run mode we report what would be fixed but do not write.
        if not is_json:
            from rich.console import Console

            console = Console()
            console.print(
                f"\n[bold]Dry-run:[/bold] {clean_stats['total_fixed']} rows "
                f"would be modified, {filter_stats['total_rows_removed']} rows "
                f"would be removed."
            )
        return stats

    # Actually write the fixed dataset
    if fix_output:
        resolved = os.path.realpath(fix_output)
        cwd = os.path.realpath(os.getcwd())
        if not resolved.startswith(cwd + os.sep) and resolved != cwd:
            raise click.BadParameter(
                f"Output path must be within current directory: {fix_output}"
            )
        filtered_dataset.save_to_disk(fix_output)
        if not is_json:
            from rich.console import Console

            console = Console()
            console.print(
                f"\n[bold green]Fixed dataset saved to:[/bold green] {fix_output}"
            )

    return stats


def _exit_code_from_report(report: Report) -> int:
    """Derive the process exit code from the report contents."""
    if report.total_errors > 0:
        return EXIT_ERROR
    if report.total_warnings > 0:
        return EXIT_WARNING
    return EXIT_OK


def _emit_error(message: str, is_json: bool) -> None:
    """Emit an error message in the appropriate format."""
    if is_json:
        JsonReporter().render_error(message)
    else:
        RichReporter().render_error(message)
