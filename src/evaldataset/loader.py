"""HuggingFace dataset loading utilities."""

from __future__ import annotations

from datasets import Dataset, load_dataset

from evaldataset.config import CheckerConfig


def load_hf_dataset(
    dataset_id: str,
    split: str = "train",
    text_field: str = "text",
    config: CheckerConfig | None = None,
) -> Dataset:
    """Load a HuggingFace dataset with optional sampling."""
    ds = load_dataset(dataset_id, split=split)

    if not isinstance(ds, Dataset):
        raise TypeError(f"Expected Dataset, got {type(ds).__name__}")

    if text_field not in ds.column_names:
        available = ", ".join(ds.column_names)
        raise ValueError(
            f"Text field '{text_field}' not found. Available: {available}"
        )

    if config and config.sample_size and config.sample_size < len(ds):
        ds = ds.shuffle(seed=42).select(range(config.sample_size))

    return ds
