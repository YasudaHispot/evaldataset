"""Integration tests for NearDuplicateChecker.

IT: NearDuplicateChecker
Source: docs/design.md — NearDuplicateChecker 受入条件 (AC-08-01, AC-08-02)
"""

from datasets import Dataset

from evaldataset.checks.duplicates import NearDuplicateChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity

# Long texts with high similarity (1 word different: "dog" vs "cat", ~87 words, Jaccard ≈ 0.886)
_SIMILAR_TEXT_A = (
    "the quick brown fox jumps over the lazy dog and runs around the park every morning "
    "before the sunrise while eating breakfast and drinking coffee while reading the newspaper "
    "on the front porch of the old farmhouse near the beautiful countryside with rolling hills "
    "and meadows full of colorful flowers swaying in the gentle breeze under the bright blue sky "
    "with white clouds floating slowly through the peaceful and serene landscape where children "
    "play happily in the garden and birds sing melodiously from the tall green trees"
)
_SIMILAR_TEXT_B = _SIMILAR_TEXT_A.replace("dog", "cat", 1)

_COMPLETELY_DIFFERENT = (
    "space exploration galaxy nebula universe planet stellar astronomy telescope "
    "quantum mechanics particle physics electron proton neutron atomic nuclear "
    "mathematical equations calculus derivatives integrals functions variables "
    "biochemistry molecules proteins enzymes cellular mitochondria chromosome "
    "geographical coordinates latitude longitude altitude topography cartography "
    "philosophical discourse epistemology metaphysics ontology phenomenology ethics"
)


class TestNearDuplicateCheckerIntegration:
    """
    IT: NearDuplicateChecker
    Source: docs/design.md — NearDuplicateChecker 受入条件 (AC-08-01, AC-08-02)
    """

    def test_near_duplicates_detected(self):
        """
        AC-08-01: 近似重複の検出

        Given: minhash_threshold=0.8 の設定で、1文字だけ違う極めて類似したテキストペアを含む Dataset
        When: NearDuplicateChecker.check(dataset, text_field="text") を実行する
        Then: severity=WARNING の Issue が1件あり、類似ペアの少なくとも一方の行インデックスが含まれる
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({"text": [_SIMILAR_TEXT_A, _SIMILAR_TEXT_B]})
        config = CheckerConfig(minhash_threshold=0.8)
        checker = NearDuplicateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        warning_issues = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warning_issues) == 1
        indices = warning_issues[0].row_indices
        assert 0 in indices or 1 in indices

    def test_different_texts_no_issues(self):
        """
        AC-08-02: 類似度が閾値未満の場合の無検出

        Given: minhash_threshold=0.8 の設定で、互いに大きく異なるテキストの Dataset
        When: NearDuplicateChecker.check(dataset, text_field="text") を実行する
        Then: CheckResult.issues が空リストである
        """
        # Arrange (Given)
        dataset = Dataset.from_dict({"text": [_SIMILAR_TEXT_A, _COMPLETELY_DIFFERENT]})
        config = CheckerConfig(minhash_threshold=0.8)
        checker = NearDuplicateChecker(config)

        # Act (When)
        result = checker.check(dataset, text_field="text")

        # Assert (Then)
        assert result.issues == []
