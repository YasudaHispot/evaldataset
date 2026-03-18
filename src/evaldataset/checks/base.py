"""Base class for dataset quality checkers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from datasets import Dataset

from evaldataset.config import CheckerConfig
from evaldataset.models import CheckResult


class BaseChecker(ABC):
    """Abstract base class for all checkers."""

    name: str = ""

    def __init__(self, config: CheckerConfig) -> None:
        self.config = config

    @abstractmethod
    def check(self, dataset: Dataset, text_field: str) -> CheckResult:
        """Run the check on the dataset and return results."""
        ...
