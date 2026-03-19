---
description: "code-reviewer、ut-validator、it-validatorをAgent Teamsで並列起動し、レビューを実施します"
---

PRまたは直近の変更に対して、Agent Teamsを使った並列レビューを実施します。

## 手順

1. **レビュー対象の特定**
   - 現在のブランチのPRが存在するか確認する
   - PRがあればそのdiffを対象とする
   - PRがなければ `git diff main...HEAD` の差分を対象とする

2. **Agent Teamsでレビューチームを起動**

   以下の3つのteammateを**並列**で起動する:

   - **code-reviewer**: コード品質、DRY/KISS、設計準拠、CLAUDE.md準拠を確認
   - **ut-validator**: `tests/unit/` のテスト品質・カバレッジを確認
   - **it-validator**: `tests/integration/` のspecトレーサビリティ、mock-policy準拠を確認

   各teammateには以下の情報を渡す:
   - レビュー対象のファイル一覧
   - 変更差分の概要
   - PR番号（存在する場合）

3. **結果の統合**

   全teammateの完了を待ち、結果を統合して報告する:

   ```
   ## レビュー結果サマリー

   ### コードレビュー（code-reviewer）
   [code-reviewerの結果要約]

   ### UT検証（ut-validator）
   [ut-validatorの結果要約]

   ### IT検証（it-validator）
   [it-validatorの結果要約]

   ### 総合判定
   - マージ可能 / 修正必要
   - 修正が必要な場合は優先順位付きリスト
   ```

4. **修正が必要な場合**
   - Major指摘がある場合は **fixer** エージェントを起動して修正を委譲する
   - fixer には各レビューアのMajor指摘（ファイルパス、指摘内容）をテキストで渡す
   - 修正完了後、コミット・プッシュする
