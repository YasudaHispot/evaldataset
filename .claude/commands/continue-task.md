---
description: "全タスクを連続して実装します"
---

## 最重要ルール: 自動継続

**タスク完了後に確認を求めたり、進捗報告で応答を終えてはいけない。**

- 1タスクのマージ完了 → 即座にフェーズ1に戻って次のタスクを開始する
- 「次に進みますか？」「残りN件です」等で止まらない
- ユーザーが明示的に停止を指示した場合のみ停止する

## アーキテクチャ: オーケストレータ / ワーカー分離

**オーケストレータ（この会話）の役割:**
- ループ制御、git操作、Agent起動、テスト実行結果の確認のみ
- コンテキストを軽量に保ち、ループ指示が圧縮されにくくする

### オーケストレータの禁止事項（厳守）

以下に違反すると、コンテキストが膨張してループ指示が圧縮され、途中停止の原因になる。

- **`src/` 配下のファイルを Read/Glob/Grep で読んではいけない**
- **`tests/` 配下のファイルを Read/Glob/Grep で読んではいけない**
- **`docs/` 配下のファイルの中身を Read で読んではいけない**（AC番号の存在確認のための `grep -c` のみ許可）
- **ソースコードの構造・関数・クラス情報を自分で調べてAgentに渡してはいけない**
- **Agentプロンプトにコードの内容を含めてはいけない** — Issue本文と参照指示だけ渡す

### オーケストレータが使ってよい操作

- `Bash`: git操作、`gh` 操作、`uv run pytest`、`grep -c`（AC存在確認）
- `Agent`: ワーカーAgent起動（テンプレートに従う）
- `Skill`: `/create-spec` 等のスキル呼び出し

**ワーカーAgent の役割:**
- Phase 2: implementer + test-writer（実装 + UT）
- Phase 3: it-writer（IT作成）
- Phase 4: code-reviewer + ut-validator + it-validator（レビュー）
- Phase 4.5: fixer（Major指摘の修正）

---

以下のフェーズを、全ての未完了タスクが完了するまで繰り返す。

## フェーズ1: タスク特定・ブランチ作成

現在のブランチを確認する。ブランチ名: `task{n}` (n:タスク番号)

### 現在のブランチがタスクのブランチの場合
対象のマージしていない状態のPRが存在するか確認する。

#### 存在する場合
  1. 現在タスクが実装中であるとして、そのタスクを対象として、フェーズ2に進む。

#### 存在しない場合
  1. タスクが完了していると判断し、mainブランチに切り替える。
  2. **現在のブランチがmainブランチの場合**に進む。

### 現在のブランチがmainブランチの場合
  1. Pullして最新にする。
  2. 未Pushのファイルがある場合は、ユーザに確認をとるため、一時停止する。
  3. **次の最も若い番号の**未完了タスク1つに対して、タスク用のブランチを作る。
  4. そのタスクを対象として、フェーズ2に進む。

### いずれのブランチでない場合
  1. ユーザーに報告する。以降の処理は行わない。

## フェーズ1.5: spec確認

`grep -c "AC-{対応番号}" docs/design.md` でACの存在を確認する（**ファイルの中身は読まない**）。

- **0件の場合**: `/create-spec` スキルを使用して受入条件を作成する
- **1件以上の場合**: スキップ

## フェーズ2: 実装 + UT（Agent Teams並列）

`gh issue view {n} --json title,body` でIssue本文を取得し、以下のテンプレートでAgentを起動する。

**implementer** と **test-writer** を並列で起動する。

### implementer プロンプトテンプレート

> GitHub Issue #{n} の実装を行ってください。
>
> ## Issue内容
> {gh issue view の title と body をそのまま貼付}
>
> ## 指示
> - CLAUDE.md を読んでプロジェクトルールを確認すること
> - docs/design.md の該当セクションと受入条件を自分で読んで設計を理解すること
> - 既存コードの構造を自分で調査すること（`src/evaldataset/` 配下）
> - テストファイルは書かないこと（test-writerが担当）

### test-writer プロンプトテンプレート

> GitHub Issue #{n} のユニットテストを作成してください。
>
> ## Issue内容
> {gh issue view の title と body をそのまま貼付}
>
> ## 指示
> - CLAUDE.md を読んでプロジェクトルールを確認すること
> - docs/design.md の該当セクションと受入条件を自分で読むこと
> - src/ の実装コードを読んでインターフェースを理解すること（UT では src 参照OK）
> - tests/unit/ 配下に配置すること
> - 既存テストのパターン（tests/unit/conftest.py 等）を参考にすること

両teammateの完了を待ち:
1. `uv run pytest tests/unit/ -v` を実行してUTが通ることを確認する
2. 必要ならcommitする

**フェーズ3への引き継ぎ**: 対象タスクのIssue番号を保持する（it-writerに渡すため）。

## フェーズ3: IT生成・実行（Agent）

**it-writer** を以下のテンプレートで起動する。

### it-writer プロンプトテンプレート

> GitHub Issue #{n} の結合テスト（IT）を作成してください。
>
> ## Issue内容
> {gh issue view の title と body をそのまま貼付}
>
> ## 指示
> - docs/design.md の該当する受入条件（Given/When/Then）を自分で読むこと
> - src/ のコードは参照禁止（specからのみ導出）
> - 正常系でのモック禁止（docs/mock-policy.md 参照）
> - tests/integration/ 配下に配置すること
> - 既存ITファイルのパターンを参考にすること
> - 各テストに Given/When/Then コメントを必須で記述すること

完了を待ち:
1. `uv run pytest tests/integration/ -v` を実行してITが通ることを確認する
2. 必要ならcommitする

## フェーズ4: レビュー（Agent Teams並列） → PR → マージ

`git diff main --name-only` で変更ファイル一覧を取得する（**ファイルの中身は読まない**）。

**code-reviewer**、**ut-validator**、**it-validator** を以下のテンプレートで並列起動する。

### code-reviewer プロンプトテンプレート

> Issue #{n} の実装をレビューしてください。
>
> 変更ファイル: {git diff main --name-only の出力}
>
> docs/design.md の受入条件と照合し、Major/Minor/Info で指摘してください。

### ut-validator プロンプトテンプレート

> Issue #{n} のユニットテストを検証してください。
>
> 変更ファイル: {git diff main --name-only の出力のうち tests/unit/ のもの}
>
> カバレッジ、アサーション妥当性、モック使用の適切さを確認し、Major/Minor/Info で指摘してください。

### it-validator プロンプトテンプレート

> Issue #{n} の結合テストを検証してください。
>
> 変更ファイル: {git diff main --name-only の出力のうち tests/integration/ のもの}
>
> specトレーサビリティ、モック禁止準拠、Given/When/Then対応を確認し、Major/Minor/Info で指摘してください。

全teammateの完了を待ち、結果を統合する:
1. Major指摘がある場合 → **fixer** を起動する。fixer にはレビュー結果のMajor指摘テキストをそのまま渡す
2. `uv run pytest tests/ -v` で全テスト通過を確認する
3. 必要ならcommitする
4. pushしてPR作成
5. PRをマージ

**即座にフェーズ1に戻る — ここで停止してはいけない。**

---

## 終了条件

- 全ての未完了タスクが完了した場合、処理を終了する。
- ユーザーが一時停止を指示した場合、処理を中断する。
