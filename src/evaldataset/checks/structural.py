"""Structural checks: missing fields, schema validation."""

from __future__ import annotations

from datasets import Dataset, Value

from evaldataset.checks.base import BaseChecker
from evaldataset.checks.registry import register
from evaldataset.config import CheckerConfig
from evaldataset.models import CheckResult, Issue, Severity


@register
class MissingFieldChecker(BaseChecker):
    """Detect rows where the text field is None or empty."""

    name = "missing_field"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)
        missing_indices: list[int] = []

        for i, row in enumerate(dataset):
            value = row.get(text_field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_indices.append(i)

        if missing_indices:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.ERROR,
                    message=f"Found {len(missing_indices)} rows with missing/empty '{text_field}'",
                    row_indices=missing_indices,
                )
            )

        result.stats = {
            "total_rows": len(dataset),
            "missing_count": len(missing_indices),
            "missing_ratio": len(missing_indices) / max(len(dataset), 1),
        }
        return result


@register
class SchemaChecker(BaseChecker):
    """Validate dataset schema: field existence and types."""

    name = "schema"

    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        result = CheckResult(checker_name=self.name)

        if text_field not in dataset.column_names:
            result.issues.append(
                Issue(
                    checker=self.name,
                    severity=Severity.ERROR,
                    message=f"Text field '{text_field}' not in schema",
                    details={"available_fields": dataset.column_names},
                )
            )
        else:
            feature = dataset.features[text_field]
            if not (isinstance(feature, Value) and feature.dtype == "string"):
                result.issues.append(
                    Issue(
                        checker=self.name,
                        severity=Severity.WARNING,
                        message=f"Text field '{text_field}' has unexpected type: {feature}",
                    )
                )

        result.stats = {
            "columns": dataset.column_names,
            "features": {k: str(v) for k, v in dataset.features.items()},
            "num_rows": len(dataset),
        }
        return result
