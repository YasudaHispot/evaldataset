"""Configuration for the CPT checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CheckerConfig:
    """Configuration for dataset quality checks."""

    # Text length thresholds
    min_length: int = 50
    max_length: int = 100_000

    # Language detection
    languages: list[str] = field(default_factory=lambda: ["en"])
    language_threshold: float = 0.5

    # Duplicate detection
    minhash_threshold: float = 0.8
    minhash_num_perm: int = 128
    skip_duplicates: bool = False

    # Sampling
    sample_size: int | None = None

    # URL/Email density
    max_url_density: float = 0.1
    max_email_density: float = 0.05

    # Token length
    token_encoding: str = "cl100k_base"
    max_token_length: int = 8192

    # Boilerplate patterns
    boilerplate_patterns: list[str] = field(
        default_factory=lambda: [
            r"(?i)^copyright\s",
            r"(?i)^all rights reserved",
            r"(?i)cookie\s*(policy|notice|consent)",
            r"(?i)privacy\s*policy",
            r"(?i)terms\s*(of|and)\s*(service|use|conditions)",
            r"(?i)subscribe\s+to\s+(our|the)\s+newsletter",
        ]
    )

    # PII patterns
    detect_pii: bool = True

    # Checkers to skip
    skip_checkers: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> CheckerConfig:
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)
