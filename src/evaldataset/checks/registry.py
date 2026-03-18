"""Checker registry for auto-discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evaldataset.checks.base import BaseChecker

_REGISTRY: dict[str, type[BaseChecker]] = {}


def register(cls: type[BaseChecker]) -> type[BaseChecker]:
    """Decorator to register a checker class."""
    _REGISTRY[cls.name] = cls
    return cls


def get_checker(name: str) -> type[BaseChecker]:
    if name not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise KeyError(f"Checker '{name}' not found. Available: {available}")
    return _REGISTRY[name]


def get_all_checkers() -> dict[str, type[BaseChecker]]:
    return dict(_REGISTRY)
