---
name: create-spec
description: "要求仕様からGiven/When/Then形式の受入条件を作成し、docs/design.mdに追記する。/research-designの簡易版で、調査・議論なしにspecのみを作成する。"
---

要求仕様（`docs/requirements.md`）と設計書（`docs/design.md`）に基づき、Given/When/Then形式の受入条件を作成します。

`/research-design` との違い: こちらは調査・議論を行わず、既存の設計情報からspecを直接導出します。新規チェッカーの設計が確定済みの場合に使用してください。

## 入力

- `docs/requirements.md` — 要求仕様
- `docs/design.md` — 設計書
- 引数（任意）: 対象FR番号またはチェッカー名（例: `FR-03-2` `HtmlResidueChecker`）

## 手順

### 1. 対象の特定

- 引数で指定された場合はそれを対象とする
- 指定がない場合は `docs/design.md` で受入条件が未定義のチェッカー/機能を対象とする

### 2. 受入条件の導出

`docs/requirements.md` の機能要件と `docs/design.md` の設計情報から、以下のケースを導出する:

1. **正常系（検出あり）**: 問題が存在するデータで正しく検出される
2. **正常系（検出なし）**: 問題がないデータで誤検出しない
3. **境界値**: 閾値ちょうどのケース（必要な場合のみ）

### 3. Given/When/Then形式で記述

```markdown
##### [チェッカー名] 受入条件 (FR-XX-X)

- Given: [前提条件]
  When: [操作]
  Then: [期待結果]
```

### 4. docs/design.mdに追記

該当チェッカーセクション内に受入条件を追記する。既存の受入条件がある場合は差分のみ追加する。

### 5. 確認

- 要求仕様の対象FR項目がすべてカバーされているか確認
- 必要ならcommitする

## 注意事項

- `src/` の実装コードは参照しない（specは仕様から導出する）
- 1 feature あたり 2-4件の受入条件に絞る
- 各受入条件にFR番号を併記する
