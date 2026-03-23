"""JSON reporter for machine-readable output."""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from evaldataset.models import Report


class JsonReporter:
    """Output report as JSON to stdout or a specified stream.

    Used when ``--output json`` is specified or when stdout is not a TTY
    (e.g. piped to another process).
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        self._stream = stream or sys.stdout

    def render(
        self,
        report: Report,
        fix_stats: dict[str, Any] | None = None,
        after_report: Report | None = None,
    ) -> None:
        """Write the report as formatted JSON to the output stream.

        When *after_report* is provided (i.e. ``--fix`` or ``--dry-run``),
        the output uses a ``before`` / ``after`` structure.  Otherwise the
        output is backward-compatible with the flat structure.

        Parameters
        ----------
        report:
            The aggregated quality check report (before fix, or the only
            report when no fix is applied).
        fix_stats:
            Optional statistics from the fix pipeline.
        after_report:
            Optional post-fix quality check report.  When present the
            JSON output uses the ``before`` / ``after`` envelope.
        """
        if after_report is not None:
            # --fix / --dry-run: before/after structure
            before_dict = report.to_dict()
            after_dict = after_report.to_dict()
            data: dict[str, Any] = {
                "dataset_id": report.dataset_id,
                "split": report.split,
                "total_rows": report.total_rows,
                "text_field": report.text_field,
                "before": {
                    "summary": before_dict["summary"],
                    "results": before_dict["results"],
                },
            }
            if fix_stats is not None:
                data["fix_stats"] = fix_stats
            data["after"] = {
                "summary": after_dict["summary"],
                "results": after_dict["results"],
            }
        else:
            # No fix: backward-compatible flat structure
            data = report.to_dict()
            if fix_stats is not None:
                data["fix_stats"] = fix_stats
        self._stream.write(json.dumps(data, ensure_ascii=False, indent=2))
        self._stream.write("\n")

    def render_error(self, message: str) -> None:
        """Write an error message as JSON to stderr.

        Parameters
        ----------
        message:
            The error description to include in the JSON object.
        """
        error_data = {"error": message}
        sys.stderr.write(json.dumps(error_data, ensure_ascii=False))
        sys.stderr.write("\n")
