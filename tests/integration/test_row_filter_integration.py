"""Integration tests for RowFilter via CLI.

IT: RowFilter
Source: docs/design.md — RowFilter 受入条件 (AC-16-01, AC-16-02, AC-16-03, AC-16-04)

RowFilter は `--fix` オプション指定時の Fix パイプライン Step 3 として動作し、
チェッカーが検出した問題行を Dataset から除去する。

テスト方法:
- CliRunner + isolated_filesystem() でカレントディレクトリを制御する
  (--fix-output はCWD内のパスのみ許可されるため)
- `--output json` で JSON 出力を取得し、`fix_stats.filter_stats` を検証する
- `datasets.load_from_disk(fix_dir)` で出力 Dataset の行数を検証する
"""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner
from datasets import Dataset, disable_progress_bars, load_from_disk

from evaldataset.cli import main

# Suppress HuggingFace progress bars in test output.
disable_progress_bars()

# ---------------------------------------------------------------------------
# Shared text constants
# ---------------------------------------------------------------------------

# AC-16-02 用: MinHash 類似度が閾値 0.8 を大幅に上回るテキストペア
# ("dog" と "cat" の 1 単語だけが異なる長文。Jaccard ≈ 0.886)
_NEAR_DUP_TEXT_A = (
    "the quick brown fox jumps over the lazy dog and runs around the park every morning "
    "before the sunrise while eating breakfast and drinking coffee while reading the newspaper "
    "on the front porch of the old farmhouse near the beautiful countryside with rolling hills "
    "and meadows full of colorful flowers swaying in the gentle breeze under the bright blue sky "
    "with white clouds floating slowly through the peaceful and serene landscape where children "
    "play happily in the garden and birds sing melodiously from the tall green trees"
)
_NEAR_DUP_TEXT_B = _NEAR_DUP_TEXT_A.replace("dog", "cat", 1)

# 近似重複とは全く異なる内容のテキスト
_DIFFERENT_TEXT = (
    "space exploration galaxy nebula universe planet stellar astronomy telescope "
    "quantum mechanics particle physics electron proton neutron atomic nuclear "
    "mathematical equations calculus derivatives integrals functions variables "
    "biochemistry molecules proteins enzymes cellular mitochondria chromosome "
    "geographical coordinates latitude longitude altitude topography cartography "
    "philosophical discourse epistemology metaphysics ontology phenomenology ethics"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parquet_dataset(ds: Dataset, base_dir: str, subdir: str = "input") -> str:
    """Persist *ds* as Parquet inside *base_dir/<subdir>/data/* and return the data path."""
    data_dir = os.path.join(base_dir, subdir, "data")
    os.makedirs(data_dir, exist_ok=True)
    ds.to_parquet(os.path.join(data_dir, "train-00000-of-00001.parquet"))
    return os.path.join(subdir, "data")


# ---------------------------------------------------------------------------
# AC-16-01: 完全一致重複行の除去
# ---------------------------------------------------------------------------


class TestRowFilterExactDuplicate:
    """
    IT: RowFilter — 完全一致重複行の除去
    Source: docs/design.md — RowFilter 受入条件 AC-16-01
    """

    def test_exact_duplicate_rows_removed(self):
        """
        AC-16-01: 完全一致重複行の除去

        Given: 同一テキストの重複行を 3 件含む 5 行の Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: 重複行が 2 件除去され、出力 Dataset が 3 行になり、
              filter_stats に exact_duplicate の除去数 2 が記録される
        """
        # Arrange (Given)
        runner = CliRunner()
        dup_text = (
            "This is a duplicate text that is long enough to pass "
            "the minimum length checker requirement for the test dataset."
        )
        # ユニークテキストは互いに完全に異なる内容にして near_duplicate を防ぐ
        unique_text_1 = _DIFFERENT_TEXT
        unique_text_2 = (
            "chemistry laboratory experiment reaction catalyst compound synthesis "
            "organic molecule atom bond electron orbital valence periodic table "
            "thermodynamics entropy enthalpy reaction kinetics equilibrium constant "
            "polymer membrane electrode solution solvent crystallization distillation "
            "spectroscopy infrared ultraviolet mass spectrometry chromatography"
        )
        ds = Dataset.from_dict({
            "text": [dup_text, dup_text, dup_text, unique_text_1, unique_text_2]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            output_data = json.loads(result.output)

            # filter_stats が fix_stats 内に存在する
            fix_stats = output_data.get("fix_stats", {})
            assert "filter_stats" in fix_stats, (
                f"'filter_stats' not found in fix_stats: {fix_stats}"
            )
            filter_stats = fix_stats["filter_stats"]

            # exact_duplicate の除去数が 2 (3件中 2件除去、1件残す)
            assert filter_stats.get("exact_duplicate") == 2, (
                f"Expected exact_duplicate=2, got {filter_stats.get('exact_duplicate')}. "
                f"filter_stats: {filter_stats}"
            )

            # 出力 Dataset が 3 行になる
            assert os.path.exists(fix_dir), (
                f"fix_dir '{fix_dir}' was not created"
            )
            fixed_ds = load_from_disk(fix_dir)
            assert len(fixed_ds) == 3, (
                f"Expected 3 rows after removing 2 exact duplicates, got {len(fixed_ds)}"
            )

    def test_filter_stats_rows_after_filter_for_exact_duplicate(self):
        """
        AC-16-01: rows_after_filter が正しく記録される

        Given: 同一テキストの重複行を 3 件含む 5 行の Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: filter_stats の rows_after_filter が 3 である
        """
        # Arrange (Given)
        runner = CliRunner()
        dup_text = (
            "Another duplicate text string that satisfies the fifty character "
            "minimum length requirement for the text length checker validation."
        )
        # ユニークテキストは互いに完全に異なる内容にして near_duplicate を防ぐ
        unique_a = _DIFFERENT_TEXT
        unique_b = (
            "architecture infrastructure engineering construction material "
            "concrete steel aluminum silicon semiconductor circuit board "
            "voltage current resistance capacitor inductor transformer relay "
            "hydraulic pneumatic mechanical structural load bearing foundation "
            "urban planning zoning regulation building code inspection permit"
        )
        ds = Dataset.from_dict({
            "text": [dup_text, dup_text, dup_text, unique_a, unique_b]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            filter_stats = output_data["fix_stats"]["filter_stats"]

            assert filter_stats.get("rows_after_filter") == 3, (
                f"Expected rows_after_filter=3, got {filter_stats.get('rows_after_filter')}. "
                f"filter_stats: {filter_stats}"
            )


# ---------------------------------------------------------------------------
# AC-16-02: 近似重複行の除去
# ---------------------------------------------------------------------------


class TestRowFilterNearDuplicate:
    """
    IT: RowFilter — 近似重複行の除去
    Source: docs/design.md — RowFilter 受入条件 AC-16-02
    """

    def test_near_duplicate_rows_removed(self):
        """
        AC-16-02: 近似重複行の除去

        Given: MinHash 類似度が閾値以上のテキストペアを含む Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: 近似重複の片方が除去され、filter_stats に near_duplicate の除去数が記録される
        """
        # Arrange (Given)
        runner = CliRunner()
        # 1 単語だけ異なる長文ペア (Jaccard ≈ 0.886、閾値 0.8 を超える)
        ds = Dataset.from_dict({
            "text": [_NEAR_DUP_TEXT_A, _NEAR_DUP_TEXT_B, _DIFFERENT_TEXT]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            output_data = json.loads(result.output)
            fix_stats = output_data.get("fix_stats", {})
            assert "filter_stats" in fix_stats, (
                f"'filter_stats' not found in fix_stats: {fix_stats}"
            )
            filter_stats = fix_stats["filter_stats"]

            # near_duplicate の除去数が 1 以上記録されている
            near_dup_removed = filter_stats.get("near_duplicate", 0)
            assert near_dup_removed >= 1, (
                f"Expected near_duplicate >= 1, got {near_dup_removed}. "
                f"filter_stats: {filter_stats}"
            )

            # 出力 Dataset の行数が入力より少ない（近似重複が除去された）
            assert os.path.exists(fix_dir), (
                f"fix_dir '{fix_dir}' was not created"
            )
            fixed_ds = load_from_disk(fix_dir)
            assert len(fixed_ds) < 3, (
                f"Expected fewer than 3 rows after near-duplicate removal, got {len(fixed_ds)}"
            )

    def test_near_duplicate_filter_stats_recorded(self):
        """
        AC-16-02: filter_stats に near_duplicate キーが存在する

        Given: MinHash 類似度が閾値以上のテキストペアを含む Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: filter_stats に near_duplicate キーが含まれる
        """
        # Arrange (Given)
        runner = CliRunner()
        ds = Dataset.from_dict({
            "text": [_NEAR_DUP_TEXT_A, _NEAR_DUP_TEXT_B, _DIFFERENT_TEXT]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            filter_stats = output_data["fix_stats"]["filter_stats"]

            assert "near_duplicate" in filter_stats, (
                f"'near_duplicate' key not found in filter_stats: {filter_stats}"
            )
            assert filter_stats["near_duplicate"] >= 1, (
                f"Expected near_duplicate >= 1, got {filter_stats['near_duplicate']}. "
                f"filter_stats: {filter_stats}"
            )


# ---------------------------------------------------------------------------
# AC-16-03: 短文/長文行のフィルタリング
# ---------------------------------------------------------------------------


class TestRowFilterTextLength:
    """
    IT: RowFilter — 短文/長文行のフィルタリング
    Source: docs/design.md — RowFilter 受入条件 AC-16-03
    """

    def test_short_text_row_removed(self):
        """
        AC-16-03: 短文/長文行のフィルタリング

        Given: min_length 未満のテキスト 1 件と正常テキスト 2 件を含む Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: 短文行が除去され、出力 Dataset が 2 行になり、
              filter_stats に text_length の除去数 1 が記録される
        """
        # Arrange (Given)
        runner = CliRunner()
        # デフォルト min_length=50 未満の短文
        short_text = "Short"
        # 2 件の正常テキストは互いに完全に異なる内容にして near_duplicate を防ぐ
        normal_text_1 = _DIFFERENT_TEXT
        normal_text_2 = (
            "cooking recipe ingredients preparation method temperature duration "
            "flour sugar butter egg milk vanilla chocolate cream baking powder "
            "cuisine tradition heritage regional specialty restaurant chef kitchen "
            "nutrition protein carbohydrate fat calorie vitamin mineral fiber "
            "fermentation preservation pickling smoking drying curing seasoning"
        )
        ds = Dataset.from_dict({"text": [short_text, normal_text_1, normal_text_2]})

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )
            output_data = json.loads(result.output)
            fix_stats = output_data.get("fix_stats", {})
            assert "filter_stats" in fix_stats, (
                f"'filter_stats' not found in fix_stats: {fix_stats}"
            )
            filter_stats = fix_stats["filter_stats"]

            # text_length の除去数が 1
            assert filter_stats.get("text_length") == 1, (
                f"Expected text_length=1, got {filter_stats.get('text_length')}. "
                f"filter_stats: {filter_stats}"
            )

            # 出力 Dataset が 2 行
            assert os.path.exists(fix_dir), (
                f"fix_dir '{fix_dir}' was not created"
            )
            fixed_ds = load_from_disk(fix_dir)
            assert len(fixed_ds) == 2, (
                f"Expected 2 rows after removing 1 short text, got {len(fixed_ds)}"
            )

    def test_short_text_filter_stats_rows_after_filter(self):
        """
        AC-16-03: rows_after_filter が正しく記録される

        Given: min_length 未満のテキスト 1 件と正常テキスト 2 件を含む Dataset と --fix オプション
        When: CLI から evaldataset <DATASET_ID> --fix --fix-output <PATH> を実行する
        Then: filter_stats の rows_after_filter が 2 である
        """
        # Arrange (Given)
        runner = CliRunner()
        short_text = "Tiny"
        normal_text_1 = _DIFFERENT_TEXT
        normal_text_2 = (
            "literature poetry novel drama prose fiction narrative character plot "
            "theme symbolism metaphor imagery rhetoric persuasion argumentation "
            "genre tragedy comedy satire allegory mythology folklore legend myth "
            "author manuscript publication edition translation adaptation criticism "
            "bibliography citation reference footnote index glossary appendix"
        )
        ds = Dataset.from_dict({"text": [short_text, normal_text_1, normal_text_2]})

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [dataset_path, "--fix", "--fix-output", fix_dir, "--output", "json"],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            filter_stats = output_data["fix_stats"]["filter_stats"]

            assert filter_stats.get("rows_after_filter") == 2, (
                f"Expected rows_after_filter=2, got {filter_stats.get('rows_after_filter')}. "
                f"filter_stats: {filter_stats}"
            )


# ---------------------------------------------------------------------------
# AC-16-04: --skip-checker によるフィルタスキップ
# ---------------------------------------------------------------------------


class TestRowFilterSkipChecker:
    """
    IT: RowFilter — --skip-checker によるフィルタスキップ
    Source: docs/design.md — RowFilter 受入条件 AC-16-04
    """

    def test_skip_exact_duplicate_checker_preserves_duplicates(self):
        """
        AC-16-04: --skip-checker によるフィルタスキップ

        Given: 重複行を含む Dataset と --fix --skip-checker exact_duplicate
              --skip-checker near_duplicate オプション
        When: CLI から evaldataset <DATASET_ID> --fix --skip-checker exact_duplicate
              --skip-checker near_duplicate --fix-output <PATH> を実行する
        Then: 重複行が除去されず、出力 Dataset の行数が入力と同じである
        """
        # Arrange (Given)
        runner = CliRunner()
        dup_text = (
            "This is a duplicate text that is long enough to pass "
            "the minimum length checker requirement for the test dataset."
        )
        unique_text_1 = _DIFFERENT_TEXT
        unique_text_2 = (
            "chemistry laboratory experiment reaction catalyst compound synthesis "
            "organic molecule atom bond electron orbital valence periodic table "
            "thermodynamics entropy enthalpy reaction kinetics equilibrium constant "
            "polymer membrane electrode solution solvent crystallization distillation "
            "spectroscopy infrared ultraviolet mass spectrometry chromatography"
        )
        ds = Dataset.from_dict({
            "text": [dup_text, dup_text, dup_text, unique_text_1, unique_text_2]
        })
        input_row_count = 5

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--skip-checker", "exact_duplicate",
                    "--skip-checker", "near_duplicate",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            assert result.exit_code in (0, 1, 2), (
                f"Unexpected exit code {result.exit_code}. Output:\n{result.output}"
            )

            # 出力 Dataset の行数が入力と同じ（除去されていない）
            assert os.path.exists(fix_dir), (
                f"fix_dir '{fix_dir}' was not created"
            )
            fixed_ds = load_from_disk(fix_dir)
            assert len(fixed_ds) == input_row_count, (
                f"Expected {input_row_count} rows (duplicates preserved with --skip-checker), "
                f"got {len(fixed_ds)}"
            )

    def test_skip_exact_duplicate_checker_filter_stats_shows_zero(self):
        """
        AC-16-04: --skip-checker exact_duplicate 時、filter_stats の exact_duplicate が 0

        Given: 重複行を含む Dataset と --fix --skip-checker exact_duplicate オプション
        When: CLI から evaldataset <DATASET_ID> --fix --skip-checker exact_duplicate を実行する
        Then: filter_stats の exact_duplicate が 0 または filter_stats が空である
        """
        # Arrange (Given)
        runner = CliRunner()
        dup_text = (
            "Repeated text content that is long enough to satisfy the minimum "
            "character count required by the text length checker configuration."
        )
        unique_text = _DIFFERENT_TEXT
        ds = Dataset.from_dict({
            "text": [dup_text, dup_text, unique_text]
        })

        with runner.isolated_filesystem():
            dataset_path = _make_parquet_dataset(ds, os.getcwd())
            fix_dir = "fixed_output"

            # Act (When)
            result = runner.invoke(
                main,
                [
                    dataset_path,
                    "--fix",
                    "--skip-checker", "exact_duplicate",
                    "--fix-output", fix_dir,
                    "--output", "json",
                ],
            )

            # Assert (Then)
            output_data = json.loads(result.output)
            fix_stats = output_data.get("fix_stats", {})

            # filter_stats が存在する場合、exact_duplicate は 0 であること
            if "filter_stats" in fix_stats:
                filter_stats = fix_stats["filter_stats"]
                assert filter_stats.get("exact_duplicate", 0) == 0, (
                    f"Expected exact_duplicate=0 when checker is skipped, "
                    f"got {filter_stats.get('exact_duplicate')}. "
                    f"filter_stats: {filter_stats}"
                )
