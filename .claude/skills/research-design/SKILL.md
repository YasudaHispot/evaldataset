---
name: research-design
description: "要求仕様に基づき、データセット検証手法の調査・設計をAgent Teamsで実施する。researcher + challenger + spec-writer を並列起動し、手法調査→反証→spec作成を行う。"
---

要求仕様（`docs/requirements.md`）に基づき、データセット検証手法の調査・設計をAgent Teamsで実施します。

## 入力

- `docs/requirements.md` — 要求仕様（FR番号で対象を特定）
- `docs/design.md` — 現在の設計状況
- 引数（任意）: 対象FR番号（例: `FR-03` `FR-04`）。省略時は未設計の全FR項目を対象とする

## 手順

### 1. 対象FR項目の特定

- 引数でFR番号が指定されている場合はそれを対象とする
- 指定がない場合は `docs/requirements.md` と `docs/design.md` を比較し、受入条件が未定義のFR項目を対象とする

### 2. Agent Teamsで調査・設計チームを起動

以下の3つのteammateを起動する:

- **researcher**: 対象FR項目の実現手法を調査（WebSearch活用）
- **challenger**: researcherの調査結果の弱点・ギャップを指摘
- **spec-writer**: 議論が収束した項目からGiven/When/Then受入条件を作成

各teammateには以下を伝える:
- 対象FR項目の一覧
- `docs/requirements.md` の参照指示
- `docs/design.md` の参照指示

### 3. 議論の促進

リードは以下を行う:
- researcher と challenger の議論を監視する
- 議論が停滞した場合は方向性を示す
- 収束した項目をspec-writerに伝える

### 4. 結果の統合

全teammateの完了を待ち、以下を確認する:
- 対象FR項目すべてに受入条件が追記されたか
- `docs/design.md` の受入条件が要求仕様と整合しているか
- 必要ならcommitする

## 成果物

- `docs/design.md` への受入条件（Given/When/Then）追記
- 調査結果のサマリー（リードが統合して報告）
