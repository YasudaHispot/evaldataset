---
name: create-tasks
description: "docs/design.mdの受入条件と実装フェーズからGitHub Issuesとしてタスクを生成する。/research-design完了後に使用。"
---

`docs/design.md` の受入条件（spec）と実装フェーズからGitHub Issuesとしてタスクを生成します。

## 入力

- `docs/design.md` — 設計書（受入条件、実装フェーズ）
- `docs/requirements.md` — 要求仕様（FR番号）
- 引数（任意）: 対象範囲（例: `Phase2` `FR-03`）。省略時は全未生成タスクを対象

## 手順

### 1. 既存タスクの確認

`gh issue list --label task` で既存のタスクIssueを取得し、重複を避ける。

### 2. タスク分解

`docs/design.md` の実装フェーズと受入条件から、以下の粒度でタスクを分解する:

**分解の基準:**
- 1タスク = 1チェッカーまたは1モジュールの実装
- 依存関係がある場合はタスク間の順序を明記
- 各タスクに対応するFR番号と受入条件を紐付ける

**タスクの構成例:**
```
タイトル: [Phase X] Checker名の実装
本文:
  ## 対象
  - FR番号: FR-XX-X
  - モジュール: src/evaldataset/checks/xxx.py

  ## 受入条件
  - Given: ...
    When: ...
    Then: ...

  ## 依存タスク
  - #N（前提タスク）
```

### 3. GitHub Issueの作成

各タスクについて以下を実行:

```bash
gh issue create \
  --title "[Phase X] タスク名" \
  --body "タスク本文" \
  --label "task"
```

- ラベル `task` を付与する（ラベルが存在しない場合は作成する）
- 依存関係がある場合は本文に依存タスクのIssue番号を記載する

### 4. タスク一覧の確認

作成したIssueの一覧を表示し、件数と概要を報告する。

## タスク分解の参考（design.mdの実装フェーズ）

```
Phase 1: 基盤（models, config, loader, base, registry, cli）
Phase 2: コアチェック（structural, text_quality, content）
Phase 3: 重複検出（duplicates, hashing）
Phase 4: レポート（builder, json, console）
Phase 5: 修正モード（fixers, pipeline）
Phase 6: 仕上げ（config yaml, エッジケース）
```

各Phaseを更に個別チェッカー/モジュール単位に分解する。
