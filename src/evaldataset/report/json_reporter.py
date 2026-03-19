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

    def render(self, report: Report, fix_stats: dict[str, Any] | None = None) -> None:
        """Write the report as formatted JSON to the output stream.

        Parameters
        ----------
        report:
            The aggregated quality check report.
        fix_stats:
            Optional statistics from the TextCleaner fix pipeline.
        """
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
