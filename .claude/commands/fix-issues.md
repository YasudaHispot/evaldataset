---
description: "ISSUEを連続して修正します。引数でISSUE番号を指定可能（例: /fix-issues #79 #80）"
---

**指定されたISSUE:** $ARGUMENTS

## 最重要ルール: 自動継続

**ISSUE修正完了後に確認を求めたり、進捗報告で応答を終えてはいけない。**

- 1つのISSUEのマージ完了 → 即座にフェーズ1に戻って次のISSUEを開始する
- ユーザーが明示的に停止を指示した場合のみ停止する

## アーキテクチャ: オーケストレータ / ワーカー分離

**オーケストレータ（この会話）の役割:**
- ループ制御、git操作、Agent起動、テスト実行結果の確認のみ
- ソースコードを直接読まない・書かない（全てAgentに委譲）

**ワーカーAgent の役割:**
- Phase 2: implementer + test-writer（修正 + UT）
- Phase 3: it-writer（IT作成）
- Phase 4: code-reviewer + ut-validator + it-validator（レビュー）
- Phase 4.5: fixer（Major指摘の修正）

---

以下のフェーズを、全てのISSUEが完了するまで繰り返す。

## フェーズ1: ISSUE特定・ブランチ作成

### 引数でISSUE番号が指定されている場合
指定されたISSUE番号をパースし、対象ISSUEリストとして保持する。指定された順序で処理する。

### 引数が指定されていない場合
全ての未修正ISSUEを対象とする。

---

現在のブランチが、ISSUEのブランチであるか確認する。ブランチ名: `fix{n}` (n:ISSUE番号)

### 現在のブランチがISSUEのブランチの場合
対象のマージしていない状態のPRが存在するか確認する。

#### 存在する場合
  1. 現在ISSUEが修正中であるとして、そのISSUEを対象として、フェーズ2に進む。

#### 存在しない場合
  1. ISSUEの修正が完了していると判断し、mainブランチに切り替える。
  2. **現在のブランチがmainブランチの場合**に進む。

### 現在のブランチがmainブランチの場合
  1. Pullして最新にする。
  2. 未Pushのファイルがある場合は、ユーザに確認をとるため、一時停止する。
  3. 対象ISSUEリストから次の未修正ISSUE 1つに対して、ブランチを作る。
  4. そのISSUEを対象として、フェーズ2に進む。

### いずれのブランチでない場合
  1. ユーザーに報告する。以降の処理は行わない。

## フェーズ1.5: spec確認

対象ISSUEに関連する受入条件（Given/When/Then）が `docs/design.md` に存在するか確認する。

- **存在しない、または修正が必要な場合**: `/create-spec` スキルを使用して受入条件を作成・更新する
- **存在する場合**: スキップ

## フェーズ2: ISSUE修正 + UT（Agent Teams並列）

**implementer** と **test-writer** を並列で起動する。

各teammateには以下を伝える:
- 対象ISSUEの内容
- `docs/design.md` の参照指示
- 担当ファイルの範囲

両teammateの完了を待ち:
1. `uv run pytest tests/unit/ -v` を実行してUTが通ることを確認する
2. 必要ならcommitする

**フェーズ3への引き継ぎ**: 対象ISSUEに関連するAC番号を保持する。

## フェーズ3: IT生成・実行（Agent）

**it-writer** を起動する。

以下を伝える:
- 対象ISSUEに関連する受入条件（AC番号と Given/When/Then の内容）
- `docs/design.md` の参照指示
- src参照禁止・モック禁止のルール
- 既存ITファイルのパターン参照指示

完了を待ち:
1. `uv run pytest tests/integration/ -v` を実行してITが通ることを確認する
2. 必要ならcommitする

## フェーズ4: レビュー（Agent Teams並列） → PR → マージ

**code-reviewer**、**ut-validator**、**it-validator** を並列で起動する。

各teammateには以下を伝える:
- 対象ISSUEの内容と対象ファイル
- `docs/design.md` の受入条件（AC番号）

全teammateの完了を待ち、結果を統合する:
1. Major指摘がある場合 → **fixer** を起動する。fixer には各レビューアのMajor指摘（ファイルパス、指摘内容）をテキストで渡す
2. `uv run pytest tests/ -v` で全テスト通過を確認する
3. 必要ならcommitする
4. pushしてPR作成
5. PRをマージ

**即座にフェーズ1に戻る — ここで停止してはいけない。**

---

## 終了条件

- 対象ISSUEリストの全ての修正が完了した場合、処理を終了する。
- ユーザーが一時停止を指示した場合、処理を中断する。
