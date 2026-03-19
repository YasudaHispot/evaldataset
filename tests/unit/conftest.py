"""Shared fixtures for unit tests."""

from __future__ import annotations

import pytest

from evaldataset.config import CheckerConfig


@pytest.fixture
def default_config() -> CheckerConfig:
    """Default CheckerConfig with standard thresholds."""
    return CheckerConfig()


@pytest.fixture
def min50_max100000_config() -> CheckerConfig:
    """CheckerConfig with min_length=50, max_length=100000 (same as defaults)."""
    return CheckerConfig(min_length=50, max_length=100_000)
