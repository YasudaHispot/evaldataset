---
name: spec-test
description: "結合テスト（IT）をspecから作成・実行する。src/は参照禁止。docs/のGiven/When/Thenから導出。"
---

結合テスト（IT）をspecに基づいて作成・実行します。

## 最重要ルール

**`src/evaldataset/` 配下の実装コードを絶対に読まない。**

テストは `docs/design.md` の受入条件（Given/When/Then）からのみ導出する。
実装の内部ロジックではなく、仕様上の振る舞いを検証する。

## 参照してよいファイル

- `docs/design.md` — 設計書・受入条件（spec）
- `docs/mock-policy.md` — モック使用ポリシー
- `configs/` — 設定ファイル
- `tests/conftest.py` — 共通フィクスチャ
- `pyproject.toml` — プロジェクト設定

## 参照してはいけないファイル

- `src/evaldataset/` 配下の全ファイル

## 作業手順

### 1. specの確認

`docs/design.md` の受入条件セクションから、対象のGiven/When/Thenを抽出する。

### 2. テスト作成

- **配置先**: `tests/integration/`
- **命名**: `test_<checker_name>_integration.py` または `test_<feature>_integration.py`
- **モック使用**: 正常系では禁止（`docs/mock-policy.md` 参照）
- **テスト数**: 1 feature あたり 1-3件の少数精鋭

### 3. トレーサビリティコメントの記述

各テストに、specへの参照を必ず記述する:

```python
class TestMissingFieldCheckerIntegration:
    """
    IT: MissingFieldChecker
    Source: docs/design.md — MissingFieldChecker 受入条件
    """

    def test_empty_text_reports_error(self, ...):
        """
        Given: textフィールドが空のレコードを含むデータセット
        When: MissingFieldCheckerを実行する
        Then: 該当レコードがIssue（severity=error）として報告される
        """
        # Arrange (Given)
        ...
        # Act (When)
        ...
        # Assert (Then)
        ...
```

### 4. テスト実行

```bash
uv run pytest tests/integration/ -v
```

### 5. テスト失敗時の判断

1. テストがspecのGiven/When/Thenに合致しているか確認
2. 合致している → **実装側のバグ**。テストは直さない。実装の修正を報告する
3. 乖離している → **テスト側を修正**する
