---
paths:
  - "**/*.py"
---

# テスト分離ルール

UT（ユニットテスト）とIT（結合テスト）を明確に分離する。

## ディレクトリ構造

```
tests/
  unit/          # UT: コンポーネント単体の検証
  integration/   # IT: specベースの結合検証
  conftest.py    # 共通フィクスチャ
```

## UT（ユニットテスト）

- **配置**: `tests/unit/`
- **目的**: 個々のコンポーネントを分離してテスト
- **src参照**: OK（実装コードを見てテストを書いてよい）
- **モック**: 許可（外部依存の分離に使用）
- **作成**: `/unit-test` スキルまたは Agent Teams の test-writer

## IT（結合テスト）

- **配置**: `tests/integration/`
- **目的**: 仕様（spec）に基づくシステム全体の動作検証
- **src参照**: 禁止（specのGiven/When/Thenから導出する）
- **モック**: 正常系では禁止（`docs/mock-policy.md` 参照）
- **作成**: `/spec-test` スキル（コンテキスト分離）
- **トレーサビリティ**: 各テストにspecへの参照コメントを記述する

## ITのトレーサビリティコメント形式

```python
class TestMissingFieldChecker:
    """
    IT: MissingFieldChecker
    Source: docs/design.md — MissingFieldChecker 受入条件
    """

    def test_empty_text_field_reports_error(self, ...):
        """
        Given: textフィールドが空のレコードを含むデータセット
        When: MissingFieldCheckerを実行する
        Then: 該当レコードがIssue（severity=error）として報告される
        """
        # Arrange (Given)
        # Act (When)
        # Assert (Then)
```

## テスト失敗時の判断ルール

1. テストがspecに基づいているか確認する
2. specに合致 → **実装側のバグ**。テストは直さない
3. specと乖離 → **テスト側を修正**する
4. 判断が難しい → 人間にエスカレーション
