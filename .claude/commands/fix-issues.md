---
description: "ISSUEを連続して修正します。引数でISSUE番号を指定可能（例: /fix-issues #79 #80）"
---

**指定されたISSUE:** $ARGUMENTS

（`$ARGUMENTS` は `#79 #80` または `79 80` のようにスペース区切り。`#` は任意。空の場合は全未修正ISSUEが対象）

## 最重要ルール

1. **自動継続**: ISSUE修正完了後に確認を求めない。マージ完了 → 即座にフェーズ1に戻る
2. **コンテキスト保護**: src/ tests/ docs/ configs/ のファイル内容を絶対に読まない。Bash経由（cat, git diff, git show等）でも読まない

この2つのルールに違反すると、コンテキストが膨張してループ指示が圧縮され、途中停止する。

## アーキテクチャ: オーケストレータ / ワーカー分離

**オーケストレータ（この会話）の役割:**
- ループ制御、git操作、Agent起動、テスト結果確認のみ

### オーケストレータの禁止事項（厳守）

- **Read/Glob/Grep でプロジェクトのファイルを読んではいけない**（src/, tests/, docs/, configs/ 全て）
- **Bash でファイル内容を表示してはいけない**（cat, head, tail, git diff（--name-onlyなし）, git show 等）
- **Agentプロンプトにコードやドキュメントの内容を含めてはいけない** — Issue番号と参照指示だけ渡す
- **Agentが失敗しても自分で実装・テスト・レビューしてはいけない**

### オーケストレータが使ってよい操作

- `Bash`: git checkout/add/commit/push, `gh issue list/view(番号取得のみ)`, `gh pr create/merge`, `uv run pytest --tb=line | tail -20`, `git diff main --name-only`, `grep -c`（AC存在確認）
- `Agent`: ワーカーAgent起動（テンプレートに従う）
- `Skill`: `/create-spec` 等

### Agent返却値のルール

Agentの返却値はオーケストレータのコンテキストに蓄積される。各Agentプロンプトに以下を必ず含める:

> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。詳細な分析やコードスニペットは応答に含めないこと。

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

`grep -c "AC-{対応番号}" docs/design.md` でACの存在を確認する（ファイルの中身は読まない）。

- **0件の場合**: `/create-spec` スキルを使用して受入条件を作成する。完了後、docs/design.md の内容は確認しない（Agentが自分で読む）
- **1件以上の場合**: スキップ

## フェーズ2: ISSUE修正 + UT（Agent Teams並列）

**注意: src/ tests/ docs/ を読まないこと。Issue番号だけAgentに渡す。**

**implementer** と **test-writer** を並列で起動する。

### implementer プロンプトテンプレート

> GitHub Issue #{n} の修正を行ってください。
>
> ## 指示
> - `gh issue view {n}` でIssue内容を自分で確認すること
> - CLAUDE.md を読んでプロジェクトルールを確認すること
> - docs/design.md の該当セクションと受入条件を自分で読んで設計を理解すること
> - 既存コードの構造を自分で調査すること
> - テストファイルは書かないこと（test-writerが担当）
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。詳細な分析やコードスニペットは応答に含めないこと。

### test-writer プロンプトテンプレート

> GitHub Issue #{n} のユニットテストを作成・更新してください。
>
> ## 指示
> - `gh issue view {n}` でIssue内容を自分で確認すること
> - CLAUDE.md を読んでプロジェクトルールを確認すること
> - docs/design.md の該当セクションと受入条件を自分で読むこと
> - src/ の実装コードを読んでインターフェースを理解すること（UT では src 参照OK）
> - tests/unit/ 配下に配置すること
> - 既存テストのパターンを参考にすること
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。詳細な分析やコードスニペットは応答に含めないこと。

両teammateの完了を待ち:
1. `uv run pytest tests/unit/ --tb=line -q | tail -20` を実行してUTが通ることを確認する
2. 必要ならcommitする

### テスト失敗時のフロー
1. pytest 出力の末尾（失敗テスト名）だけ確認する
2. **fixer** を起動し、pytest 出力をそのまま渡す（自分でコードを読んで原因調査しない）
3. fixer 完了後、再度 pytest を実行する
4. 2回失敗した場合はユーザーに報告して停止する

## フェーズ3: IT生成・実行（Agent）

**注意: src/ tests/ docs/ を読まないこと。Issue番号だけAgentに渡す。**

**it-writer** を起動する。

### it-writer プロンプトテンプレート

> GitHub Issue #{n} の結合テスト（IT）を作成・更新してください。
>
> ## 指示
> - `gh issue view {n}` でIssue内容を自分で確認すること
> - docs/design.md の該当する受入条件（Given/When/Then）を自分で読むこと
> - src/ のコードは参照禁止（specからのみ導出）
> - 正常系でのモック禁止（docs/mock-policy.md 参照）
> - tests/integration/ 配下に配置すること
> - 既存ITファイルのパターンを参考にすること
> - 各テストに Given/When/Then コメントを必須で記述すること
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。詳細な分析やコードスニペットは応答に含めないこと。

完了を待ち:
1. `uv run pytest tests/integration/ --tb=line -q | tail -20` を実行してITが通ることを確認する
2. 必要ならcommitする
3. テスト失敗時は**フェーズ2のテスト失敗時のフロー**に従う

## フェーズ4: レビュー（Agent Teams並列） → PR → マージ

**注意: src/ tests/ docs/ を読まないこと。**

`git diff main --name-only` で変更ファイル一覧を取得する（ファイルの中身は読まない）。

**code-reviewer**、**ut-validator**、**it-validator** を並列起動する。

### code-reviewer プロンプトテンプレート

> Issue #{n} の実装をレビューしてください。
>
> 変更ファイル: {git diff main --name-only の出力}
>
> docs/design.md の受入条件と照合し、Major/Minor/Info で指摘してください。
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。Major指摘がある場合は指摘内容（ファイルパスと1行説明）のみ列挙すること。

### ut-validator プロンプトテンプレート

> Issue #{n} のユニットテストを検証してください。
>
> 変更ファイル: {git diff main --name-only の出力のうち tests/unit/ のもの}
>
> カバレッジ、アサーション妥当性、モック使用の適切さを確認し、Major/Minor/Info で指摘してください。
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。Major指摘がある場合は指摘内容（ファイルパスと1行説明）のみ列挙すること。

### it-validator プロンプトテンプレート

> Issue #{n} の結合テストを検証してください。
>
> 変更ファイル: {git diff main --name-only の出力のうち tests/integration/ のもの}
>
> specトレーサビリティ、モック禁止準拠、Given/When/Then対応を確認し、Major/Minor/Info で指摘してください。
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。Major指摘がある場合は指摘内容（ファイルパスと1行説明）のみ列挙すること。

全teammateの完了を待ち、結果を統合する:
1. Major指摘がある場合 → **fixer** を起動する
2. `uv run pytest tests/ --tb=line -q | tail -20` で全テスト通過を確認する
3. 必要ならcommitする
4. pushしてPR作成
5. PRをマージ

### fixer プロンプトテンプレート

> Issue #{n} のレビューでMajor指摘がありました。修正してください。
>
> ## Major指摘
> {code-reviewer/ut-validator/it-validator の返却値からMajor指摘のみ抜粋}
>
> ## 指示
> - CLAUDE.md を読んでプロジェクトルールを確認すること
> - 指摘されたファイルを自分で読んで修正すること
> - 修正後 `uv run pytest tests/ -v` でテストが通ることを確認すること
>
> **応答形式**: 最終応答は10行以内のサマリーのみ返すこと。

### Agent失敗時のフロー
1. 同じテンプレートで再度Agentを起動する（最大2回）
2. 2回失敗した場合はユーザーに報告して停止する
3. **自分で実装・テスト作成・レビューを行ってはいけない**

**即座にフェーズ1に戻る — ここで停止してはいけない。**

---

## 終了条件

- 対象ISSUEリストの全ての修正が完了した場合、処理を終了する。
- ユーザーが一時停止を指示した場合、処理を中断する。

---

## 再確認: オーケストレータの禁止事項

以下を絶対に行わないこと:
- src/ tests/ docs/ configs/ のファイルを読む（Read, Glob, Grep, cat, git diff, git show 等すべて）
- Agentプロンプトにコードやドキュメントの内容を含める
- Agentが失敗した場合に自分で代行する
