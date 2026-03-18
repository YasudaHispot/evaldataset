"""Data models for check results and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """A single quality issue found in the dataset."""

    checker: str
    severity: Severity
    message: str
    row_indices: list[int] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checker": self.checker,
            "severity": self.severity.value,
            "message": self.message,
            "affected_rows": len(self.row_indices),
            "sample_indices": self.row_indices[:10],
            "details": self.details,
        }


@dataclass
class CheckResult:
    """Result from a single checker run."""

    checker_name: str
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checker": self.checker_name,
            "issues": [i.to_dict() for i in self.issues],
            "stats": self.stats,
        }


@dataclass
class Report:
    """Aggregated report from all checkers."""

    dataset_id: str
    split: str
    total_rows: int
    text_field: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return sum(len(r.issues) for r in self.results)

    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.results)

    @property
    def total_warnings(self) -> int:
        return sum(r.warning_count for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "split": self.split,
            "total_rows": self.total_rows,
            "text_field": self.text_field,
            "summary": {
                "total_issues": self.total_issues,
                "errors": self.total_errors,
                "warnings": self.total_warnings,
            },
            "results": [r.to_dict() for r in self.results],
        }
