"""Shared fixtures for integration tests.

Provides local Parquet-backed datasets for CLI integration tests,
eliminating the need to mock ``load_hf_dataset`` in normal-path tests.

Each fixture creates a temporary directory containing a single Parquet
file and returns the directory path (str) which can be passed directly
as the ``DATASET_ID`` argument to the CLI.
"""

from __future__ import annotations

import pytest
from datasets import Dataset, disable_progress_bars

# Suppress HuggingFace datasets progress bars globally so that tqdm output
# does not pollute CliRunner's captured stdout during integration tests.
disable_progress_bars()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_dataset_to_parquet(dataset: Dataset, tmp_path) -> str:
    """Persist *dataset* as a Parquet file inside a ``data/`` sub-directory.

    A sub-directory is used so that fixtures and the test function can
    both use ``tmp_path`` without interfering with each other (e.g. a
    YAML config written by the test won't be in the dataset directory).
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    dataset.to_parquet(str(data_dir / "train-00000-of-00001.parquet"))
    return str(data_dir)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_dataset_path(tmp_path) -> str:
    """5-row clean dataset with no quality issues.

    Each text is >50 characters, English, and unique (avoids
    near-duplicate warnings).
    """
    unique_contents = [
        "The quick brown fox jumps over the lazy dog with agility and grace.",
        "Machine learning algorithms process large amounts of data efficiently.",
        "Natural language processing enables computers to understand human speech.",
        "Data science combines statistics, mathematics, and programming effectively.",
        "Cloud computing provides scalable infrastructure for modern applications.",
    ]
    texts = [content + f" Document {i}." for i, content in enumerate(unique_contents)]
    ds = Dataset.from_dict({"text": texts})
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def warning_dataset_path(tmp_path) -> str:
    """2-row dataset containing a short text that triggers TextLengthChecker WARNING."""
    ds = Dataset.from_dict({
        "text": [
            "Short",  # <50 chars -> WARNING
            "This is a normal document with sufficient text length for quality checks.",
        ]
    })
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def error_dataset_path(tmp_path) -> str:
    """2-row dataset with a None text field that triggers MissingFieldChecker ERROR."""
    ds = Dataset.from_dict({
        "text": [None, "Normal text with sufficient length for quality checks."]
    })
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def html_control_chars_dataset_path(tmp_path) -> str:
    """3-row dataset with HTML tags and control characters (for --fix / --dry-run tests)."""
    ds = Dataset.from_dict({
        "text": [
            "<p>Hello <b>world</b></p>",
            "Text with\x00control chars",
            "Normal clean text without any issues at all.",
        ]
    })
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def long_text_dataset_path_5001(tmp_path) -> str:
    """2-row dataset: one 5001-char text + one normal text."""
    ds = Dataset.from_dict({
        "text": [
            "x" * 5001,
            "This is a normal document with sufficient text length for quality checks.",
        ]
    })
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def long_text_dataset_path_5000(tmp_path) -> str:
    """2-row dataset: one exactly-5000-char text + one normal text."""
    ds = Dataset.from_dict({
        "text": [
            "x" * 5000,
            "This is a normal document with sufficient text length for quality checks.",
        ]
    })
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def near_duplicate_dataset_path(tmp_path) -> str:
    """2-row dataset with nearly identical texts for NearDuplicateChecker detection."""
    base = "word " * 100  # 100-word identical content
    variant = base[:-1] + "X"  # last char differs
    ds = Dataset.from_dict({"text": [base, variant]})
    return _save_dataset_to_parquet(ds, tmp_path)


@pytest.fixture()
def large_dataset_path(tmp_path) -> str:
    """1,100+ row dataset for --sample-size tests (AC-14-04 requires 1,000+)."""
    ds = Dataset.from_dict({
        "text": [
            f"This is document number {i:04d}, a unique entry in this large dataset. "
            "It has sufficient length to pass the text length checker "
            "and contains absolutely no quality issues whatsoever."
            for i in range(1100)
        ]
    })
    return _save_dataset_to_parquet(ds, tmp_path)
