# 設計書

## 概要

CPT（Continued Pre-Training）用 Arrow/Parquet 形式データセットの品質チェック・自動修正 CLI の設計。

チェッカーは `BaseChecker` を継承し、`@register` デコレータでレジストリに登録する。
CLI エントリポイント (`evaldataset.cli:main`) がレジストリから全チェッカーを取得して順次実行し、`Report` として集約する。

---

## 終了コード

| コード | 意味 |
|-------|------|
| 0 | 問題なし（WARNING/ERROR ゼロ） |
| 1 | WARNING 以上の Issue が 1 件以上検出された |
| 2 | ERROR の Issue が 1 件以上検出された |
| 3 | 実行エラー（データセット読み込み失敗、設定エラー等） |

---

## チェッカー実行戦略

- **実行順序**: レジストリ登録順に全チェッカーを順次実行する（best-effort 方式）
- **エラー伝播**: 1 つのチェッカーが例外を投げた場合、その結果を ERROR として記録し、残りのチェッカーの実行を継続する
- **チェッカー間依存**: `SchemaChecker` が `text_field` 不在の ERROR を出した場合、後続のテキスト系チェッカーはスキップする（フィールド参照で全件失敗するため）
- **空行スキップ**: `MissingFieldChecker` が検出した欠損行インデックスは、後続チェッカーに渡してスキップ対象とする

---

## 実装フェーズ

| フェーズ | 実装対象 |
|---------|---------|
| P1 (完了) | MissingFieldChecker, SchemaChecker, loader, models |
| P2 | TextLengthChecker, LanguageChecker, HTMLChecker, MojibakeChecker |
| P3 | ExactDuplicateChecker, NearDuplicateChecker |
| P4 | PiiChecker, TokenLengthChecker, BoilerplateChecker |
| P5 | TextCleaner (自動修正 Fixer) |
| P6 | CLI (`evaldataset` コマンド)、YAML 設定読み込み、レポート出力 |

---

## チェッカー一覧

### 構造チェッカー

---

#### MissingFieldChecker

**目的**: テキストフィールドが `None` または空文字列のレコードを検出する。

**実装**: `src/evaldataset/checks/structural.py` (P1 完了)

**受入条件**:

- AC-01-01: 空・None フィールドの検出
  - Given: `text` フィールドが `None` のレコード 1 件と空文字列のレコード 1 件（合計 2 件）、正常なレコード 3 件を含む Dataset
  - When: `MissingFieldChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` に severity=ERROR の Issue が 1 件あり、`row_indices` に 2 件のインデックスが含まれ、`stats["missing_count"]` が 2 である

- AC-01-02: 正常データでの無検出
  - Given: 全レコードの `text` フィールドが非空文字列の Dataset（5 件）
  - When: `MissingFieldChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストであり、`stats["missing_count"]` が 0 である

- AC-01-03: 空白のみのテキストを欠損として扱う
  - Given: `text` フィールドが `"   "` （空白のみ）のレコード 1 件を含む Dataset
  - When: `MissingFieldChecker.check(dataset, text_field="text")` を実行する
  - Then: 該当レコードが欠損と判定され、`stats["missing_count"]` が 1 である

---

#### SchemaChecker

**目的**: Dataset のスキーマを検証し、テキストフィールドの存在と型を確認する。

**実装**: `src/evaldataset/checks/structural.py` (P1 完了)

**受入条件**:

- AC-02-01: テキストフィールド不在の検出
  - Given: `text` 列を持たない Dataset（`content` 列のみ）
  - When: `SchemaChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` に severity=ERROR の Issue が 1 件あり、`details["available_fields"]` に実際の列名が含まれる

- AC-02-02: 型の不一致の検出
  - Given: `text` 列が string 型でない Dataset（int32 型など）
  - When: `SchemaChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` に severity=WARNING の Issue が 1 件ある

- AC-02-03: 正常スキーマでの無検出
  - Given: `text` 列が `Value(dtype='string')` 型の Dataset
  - When: `SchemaChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストであり、`stats["columns"]` に `"text"` が含まれる

---

### テキスト品質チェッカー

---

#### TextLengthChecker

**目的**: テキスト長が `min_length`（デフォルト 50）未満または `max_length`（デフォルト 100,000）超のレコードを検出する。

**実装**: `src/evaldataset/checks/text_quality.py` (P2)

**受入条件**:

- AC-03-01: 短すぎるテキストの検出
  - Given: `min_length=50` の設定で、49 文字のテキストを含むレコード 1 件と 50 文字以上のレコード 4 件を含む Dataset
  - When: `TextLengthChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、`row_indices` に 49 文字レコードのインデックスが含まれる

- AC-03-02: 境界値（ちょうど min_length）での無検出
  - Given: `min_length=50` の設定で、ちょうど 50 文字のテキストを含む Dataset
  - When: `TextLengthChecker.check(dataset, text_field="text")` を実行する
  - Then: WARNING の Issue が発生しない（50 文字は許容範囲）

- AC-03-03: 長すぎるテキストの検出
  - Given: `max_length=100000` の設定で、100,001 文字のテキストを含むレコード 1 件を含む Dataset
  - When: `TextLengthChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、該当レコードの `row_indices` が含まれる

---

#### LanguageChecker

**目的**: 許可言語（デフォルト `["en"]`）以外の言語が `language_threshold`（デフォルト 0.5）を超えて含まれるレコードを検出する。

**実装**: `src/evaldataset/checks/text_quality.py` (P2)、`fast-langdetect` を使用

**受入条件**:

- AC-04-01: 許可外言語の検出
  - Given: `languages=["en"]`, `language_threshold=0.5` の設定で、日本語テキストのレコード 1 件と英語テキストのレコード 4 件を含む Dataset
  - When: `LanguageChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、日本語レコードの行インデックスが含まれる

- AC-04-02: 許可言語での無検出
  - Given: `languages=["en"]` の設定で、全レコードが英語テキストの Dataset
  - When: `LanguageChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

#### HTMLChecker

**目的**: HTML タグが多数残存するテキストを検出する。

**実装**: `src/evaldataset/checks/text_quality.py` (P2)、`utils/text.py:count_html_tags` を使用

**受入条件**:

- AC-05-01: HTML タグ混入の検出
  - Given: `<p>` `<div>` `<span>` 等の HTML タグが 5 件以上含まれるテキストのレコードを含む Dataset
  - When: `HTMLChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が発生し、該当レコードのインデックスが含まれる

- AC-05-02: タグなしテキストでの無検出
  - Given: HTML タグを一切含まないプレーンテキストの Dataset
  - When: `HTMLChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

#### MojibakeChecker

**目的**: 文字化け（mojibake）が疑われるテキストを検出する。

**実装**: `src/evaldataset/checks/text_quality.py` (P2)、`utils/text.py:has_mojibake` / `ftfy` を使用

**受入条件**:

- AC-06-01: 文字化けテキストの検出
  - Given: `ftfy.fix_text` で修正が発生するテキスト（例: `"â€œhelloâ€"`）を含むレコードの Dataset
  - When: `MojibakeChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件以上あり、該当レコードのインデックスが含まれる

- AC-06-02: 正常テキストでの無検出
  - Given: `ftfy.fix_text` で変化しない正常な UTF-8 テキストの Dataset
  - When: `MojibakeChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

### 重複チェッカー

---

#### ExactDuplicateChecker

**目的**: SHA-256 ハッシュにより完全一致の重複レコードを検出する。

**実装**: `src/evaldataset/checks/duplicates.py` (P3)、`utils/hashing.py:sha256_hash` を使用

**受入条件**:

- AC-07-01: 完全一致重複の検出
  - Given: 同一テキスト "Hello world" を持つレコードが 3 件、ユニークなレコード 2 件を含む Dataset（計 5 件）
  - When: `ExactDuplicateChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、`row_indices` に重複 3 件のインデックスが含まれ、`stats["duplicate_count"]` が 3 である

- AC-07-02: 重複なしデータでの無検出
  - Given: 全レコードのテキストがそれぞれ異なる Dataset
  - When: `ExactDuplicateChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストであり、`stats["duplicate_count"]` が 0 である

- AC-07-03: `skip_duplicates=True` 時のスキップ
  - Given: `skip_duplicates=True` の設定で、重複レコードを含む Dataset
  - When: `ExactDuplicateChecker.check(dataset, text_field="text")` を実行する
  - Then: Issue が生成されず、`stats` に `"skipped": True` が含まれる

---

#### NearDuplicateChecker

**目的**: MinHash により `minhash_threshold`（デフォルト 0.8）を超えるジャカード類似度の近似重複レコードを検出する。

**実装**: `src/evaldataset/checks/duplicates.py` (P3)、`datasketch` を使用

**受入条件**:

- AC-08-01: 近似重複の検出
  - Given: `minhash_threshold=0.8` の設定で、1 文字だけ違う極めて類似したテキストペアを含む Dataset
  - When: `NearDuplicateChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、類似ペアの少なくとも一方の行インデックスが含まれる

- AC-08-02: 類似度が閾値未満の場合の無検出
  - Given: `minhash_threshold=0.8` の設定で、互いに大きく異なるテキストの Dataset
  - When: `NearDuplicateChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

### コンテンツ品質チェッカー

---

#### PiiChecker

**目的**: メールアドレス・電話番号・SSN・クレジットカード番号・IP アドレス等の PII（個人情報）を含むレコードを検出する。

**実装**: `src/evaldataset/checks/content.py` (P4)、`utils/pii.py:detect_pii` を使用

**受入条件**:

- AC-09-01: PII（メールアドレス）の検出
  - Given: `detect_pii=True` の設定で、`user@example.com` を含むテキストのレコード 1 件を含む Dataset
  - When: `PiiChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、`details` に `pii_type: "email"` の情報が含まれる

- AC-09-02: `detect_pii=False` 時のスキップ
  - Given: `detect_pii=False` の設定で、PII を含む Dataset
  - When: `PiiChecker.check(dataset, text_field="text")` を実行する
  - Then: Issue が生成されない

- AC-09-03: PII なしデータでの無検出
  - Given: `detect_pii=True` の設定で、PII パターンを一切含まないテキストの Dataset
  - When: `PiiChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

#### TokenLengthChecker

**目的**: `cl100k_base` エンコーディングでトークン数が `max_token_length`（デフォルト 8192）を超えるレコードを検出する。

**実装**: `src/evaldataset/checks/content.py` (P4)、`tiktoken` を使用

**受入条件**:

- AC-10-01: トークン数超過の検出
  - Given: `max_token_length=8192`, `token_encoding="cl100k_base"` の設定で、8,193 トークン相当のテキストを含むレコードの Dataset
  - When: `TokenLengthChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件あり、該当レコードのインデックスと実際のトークン数が `details` に含まれる

- AC-10-02: 境界値（ちょうど max_token_length）での無検出
  - Given: `max_token_length=8192` の設定で、ちょうど 8,192 トークンのテキストを含む Dataset
  - When: `TokenLengthChecker.check(dataset, text_field="text")` を実行する
  - Then: Issue が発生しない（8,192 トークンは許容範囲）

---

#### BoilerplateChecker

**目的**: "Copyright", "Cookie Policy" 等のボイラープレートパターンにマッチするテキストを検出する。

**実装**: `src/evaldataset/checks/content.py` (P4)、`CheckerConfig.boilerplate_patterns` を使用

**受入条件**:

- AC-11-01: ボイラープレートの検出
  - Given: デフォルト `boilerplate_patterns` の設定で、`"Copyright 2023 Example Corp"` から始まるテキストのレコードを含む Dataset
  - When: `BoilerplateChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=INFO の Issue が 1 件あり、マッチしたパターンが `details` に含まれる

- AC-11-02: URL/Email 密度超過の検出
  - Given: `max_url_density=0.1` の設定で、テキスト長の 15% が URL 文字で占められるレコードを含む Dataset
  - When: `BoilerplateChecker.check(dataset, text_field="text")` を実行する
  - Then: severity=WARNING の Issue が 1 件ある

- AC-11-03: 正常テキストでの無検出
  - Given: ボイラープレートパターンも高密度 URL も含まないテキストの Dataset
  - When: `BoilerplateChecker.check(dataset, text_field="text")` を実行する
  - Then: `CheckResult.issues` が空リストである

---

### 自動修正（Fixer）

---

#### TextCleaner

**目的**: 検出された問題を自動修正する。HTML タグ除去・制御文字除去・過剰空白の正規化・mojibake 修正を行う。

**実装**: `src/evaldataset/fixer.py` (P5)、`utils/text.py` の各ユーティリティを使用

**修正パイプライン（適用順序）**:

1. 文字化け修正（`ftfy.fix_text`）— Unicode 正規化を含む
2. HTML タグ除去（`BeautifulSoup.get_text`）— script/style タグの完全除去
3. 制御文字除去（正規表現）— `\t`, `\n`, `\r` は保持
4. 過剰空白の正規化（正規表現）— 連続空白・改行の正規化、先頭末尾の空白除去

**設計原則**:
- 修正前のデータは保持する（`--dry-run` で変更内容をプレビュー可能）
- 各修正ステップで影響行数を統計として記録する
- 近似重複の自動除去はデフォルト無効（誤って有用なデータを削除するリスク回避）

**受入条件**:

- AC-12-01: HTML タグの除去
  - Given: `<p>Hello <b>world</b></p>` のような HTML タグを含むテキスト
  - When: `TextCleaner.fix_text(text)` を実行する
  - Then: 戻り値が `"Hello world"` のように HTML タグを含まないプレーンテキストになる

- AC-12-02: 制御文字の除去
  - Given: タブ（`\t`）と改行（`\n`）以外の制御文字（例: `\x00`, `\x08`）を含むテキスト
  - When: `TextCleaner.fix_text(text)` を実行する
  - Then: 制御文字が除去され、`\t` と `\n` はそのまま保持される

- AC-12-03: mojibake の修正
  - Given: `ftfy.fix_text` で修正可能な文字化けテキスト
  - When: `TextCleaner.fix_text(text)` を実行する
  - Then: 戻り値が `ftfy.fix_text` の出力と一致する

- AC-12-04: `--fix` オプションでの Dataset 全体修正
  - Given: HTML タグや制御文字を含む複数レコードの Dataset と `--fix` オプション
  - When: CLI から `evaldataset <DATASET_ID> --fix` を実行する
  - Then: 修正済み Dataset が出力先に保存され、`Report` に修正件数が記録される

---

#### RowFilter

**目的**: チェッカーが検出した問題行（`Issue.row_indices`）を使い、該当行を Dataset から除去する。TextCleaner（テキスト変換）の後に適用する。

**実装**: `src/evaldataset/fixer.py` に `RowFilter` クラスを追加

**パイプライン順序**:

```
1. TextCleaner（既存: テキスト変換）
2. チェッカー実行（クリーニング後のデータに対して）
3. RowFilter（新規: 問題行の除去）
```

TextCleaner を先に適用することで、クリーニングで解消される問題（HTML残留等）を除外し、クリーニング後にも残る問題（短文、重複等）のみをフィルタリング対象にする。

**フィルタリング対象**:

| フィルタ | 対応チェッカー | 除去対象 |
|---------|-------------|---------|
| 完全一致重複の除去 | `ExactDuplicateChecker` | 重複行（最初の 1 件を残す） |
| 近似重複の除去 | `NearDuplicateChecker` | 類似行（最初の 1 件を残す） |
| 短文/長文のフィルタリング | `TextLengthChecker` | `min_length` 未満 / `max_length` 超過の行 |
| PII を含む行の除去 | `PiiChecker` | PII（メールアドレス等）を含む行 |

**統計出力**: `filter_stats` として以下を記録する:
- 各チェッカー名ごとの除去行数
- `total_rows_removed`: 除去された総行数（重複カウントなし）
- `rows_after_filter`: フィルタリング後の行数

**受入条件**:

- AC-16-01: 完全一致重複行の除去
  - Given: 同一テキストの重複行を 3 件含む 5 行の Dataset と `--fix` オプション
  - When: CLI から `evaldataset <DATASET_ID> --fix --fix-output <PATH>` を実行する
  - Then: 重複行が 2 件除去され、出力 Dataset が 3 行になり、`filter_stats` に `exact_duplicate` の除去数 2 が記録される

- AC-16-02: 近似重複行の除去
  - Given: MinHash 類似度が閾値以上のテキストペアを含む Dataset と `--fix` オプション
  - When: CLI から `evaldataset <DATASET_ID> --fix --fix-output <PATH>` を実行する
  - Then: 近似重複の片方が除去され、`filter_stats` に `near_duplicate` の除去数が記録される

- AC-16-03: 短文/長文行のフィルタリング
  - Given: `min_length` 未満のテキスト 1 件と正常テキスト 2 件を含む Dataset と `--fix` オプション
  - When: CLI から `evaldataset <DATASET_ID> --fix --fix-output <PATH>` を実行する
  - Then: 短文行が除去され、出力 Dataset が 2 行になり、`filter_stats` に `text_length` の除去数 1 が記録される

- AC-16-04: `--skip-checker` によるフィルタスキップ
  - Given: 重複行を含む Dataset と `--fix --skip-checker exact_duplicate` オプション
  - When: CLI から実行する
  - Then: 重複行が除去されず、出力 Dataset の行数が入力と同じである

---

### レポート出力

---

#### Report

**目的**: 全チェッカーの結果を集約し、コンソールへの人間可読出力と JSON 出力の両方を提供する。

**実装**: `src/evaldataset/models.py` (P1 完了)、CLI レポーター (P6)

**受入条件**:

- AC-13-01: JSON 出力の正確性
  - Given: 2 件の ERROR と 3 件の WARNING を含む `Report` オブジェクト
  - When: `report.to_dict()` を呼び出す
  - Then: `summary.errors == 2`, `summary.warnings == 3`, `summary.total_issues == 5` を含む辞書が返される

- AC-13-02: `--output json` でのマシン可読出力
  - Given: 品質問題を含む Dataset と `--output json` オプション
  - When: CLI から `evaldataset <DATASET_ID> --output json` を実行する
  - Then: stdout に有効な JSON が出力され、`summary`, `results` キーが含まれる

- AC-13-03: リッチコンソール出力（デフォルト）
  - Given: 品質問題を含む Dataset
  - When: CLI から `evaldataset <DATASET_ID>` を実行する（`--output` 未指定）
  - Then: Rich によるテーブル形式でチェッカー名・Issue 数・重大度が表示される

---

### CLI

---

#### `evaldataset` コマンド

**目的**: HuggingFace データセット ID を引数に取り、チェックを実行してレポートを出力する。

**実装**: `src/evaldataset/cli.py` (P6)、`click` を使用

**CLIオプション一覧**:

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `DATASET_ID` (引数) | 必須 | HuggingFace Hub のデータセット ID |
| `--split` | `train` | 対象スプリット |
| `--text-field` | `text` | テキストフィールド名 |
| `--config` | なし | YAML 設定ファイルパス |
| `--output` | `rich` | 出力形式 (`rich` / `json`) |
| `--fix` | False | 自動修正を実行する |
| `--fix-output` | なし | 修正済み Dataset の出力先 |
| `--sample-size` | なし | サンプリング件数 |
| `--skip-checker` | [] | スキップするチェッカー名（複数指定可） |
| `--dry-run` | False | 変更なしで修正対象を確認する |

**受入条件**:

- AC-14-01: 正常実行（基本フロー）
  - Given: HuggingFace Hub 上の有効なデータセット ID で、品質問題がないデータセット
  - When: `evaldataset <DATASET_ID>` を実行する
  - Then: 終了コード 0 で完了し、全チェッカーの結果がコンソールに表示される

- AC-14-01b: 品質問題検出時の終了コード
  - Given: WARNING 以上の Issue を含むデータセット
  - When: `evaldataset <DATASET_ID>` を実行する
  - Then: 終了コード 1（WARNING のみ）または 2（ERROR あり）で終了する

- AC-14-02: 不正なデータセット ID でのエラー終了
  - Given: 存在しないデータセット ID `"nonexistent/dataset-xyz"`
  - When: `evaldataset nonexistent/dataset-xyz` を実行する
  - Then: 終了コード 3（実行エラー）で終了し、エラーメッセージが stderr に出力される

- AC-14-03: `--output json` でのマシン可読出力
  - Given: 有効なデータセット ID と `--output json` オプション
  - When: `evaldataset <DATASET_ID> --output json` を実行する
  - Then: stdout に有効な JSON が出力される（exit code は問題の有無に応じて 0/1/2）

- AC-14-03b: TTY 非接続時の自動 JSON 出力
  - Given: 有効なデータセット ID で stdout が TTY でない環境（パイプ等）
  - When: `evaldataset <DATASET_ID> | cat` を実行する
  - Then: `--output json` 未指定でも JSON 形式で stdout に出力される

- AC-14-04: `--sample-size` によるサンプリング
  - Given: 1,000 件以上のデータセットと `--sample-size 100`
  - When: `evaldataset <DATASET_ID> --sample-size 100` を実行する
  - Then: 100 件のサブセットに対してチェックが実行され、`Report.total_rows` が 100 である

- AC-14-05: `--dry-run` での変更なし確認
  - Given: 品質問題を含む Dataset と `--fix --dry-run` オプション
  - When: `evaldataset <DATASET_ID> --fix --dry-run` を実行する
  - Then: 修正対象レコード一覧が出力されるが、実際のファイル書き込みは行われない

- AC-14-06: 制御文字を含む入力の拒否
  - Given: DATASET_ID 引数に制御文字（`\x00` 等）を含む入力
  - When: `evaldataset` コマンドを実行する
  - Then: 終了コード 1 でエラーメッセージが出力され、処理が開始されない

---

### 設定

---

#### CheckerConfig と YAML 設定ファイル

**目的**: チェッカーの動作を YAML ファイルまたは CLI オプションでカスタマイズ可能にする。

**実装**: `src/evaldataset/config.py` (P1 完了)、CLI 統合 (P6)

**デフォルト設定値**:

| 設定キー | デフォルト値 | 説明 |
|---------|------------|------|
| `min_length` | 50 | テキスト最小文字数 |
| `max_length` | 100000 | テキスト最大文字数 |
| `languages` | `["en"]` | 許可言語コードリスト |
| `language_threshold` | 0.5 | 言語検出信頼度閾値 |
| `minhash_threshold` | 0.8 | 近似重複判定のジャカード類似度閾値 |
| `minhash_num_perm` | 128 | MinHash 置換数 |
| `skip_duplicates` | False | 重複チェックのスキップフラグ |
| `max_url_density` | 0.1 | URL 文字密度の上限 |
| `max_email_density` | 0.05 | Email 文字密度の上限 |
| `token_encoding` | `"cl100k_base"` | tiktoken エンコーディング名 |
| `max_token_length` | 8192 | トークン数の上限 |
| `detect_pii` | True | PII 検出の有効フラグ |
| `skip_checkers` | `[]` | スキップするチェッカー名リスト |

**設定マージの優先順位**（高い順）:

1. CLI オプション（`--min-length 100` 等）
2. YAML 設定ファイル（`--config config.yaml`）
3. デフォルト値（`CheckerConfig` の dataclass デフォルト）

**受入条件**:

- AC-15-01: YAML ファイルからの設定読み込み
  - Given: `min_length: 100` を含む YAML ファイル
  - When: `CheckerConfig.from_yaml(path)` を実行する
  - Then: `config.min_length == 100` であり、他のフィールドはデフォルト値のままである

- AC-15-02: 未知キーの無視
  - Given: `CheckerConfig` に存在しないキー `unknown_key: value` を含む YAML ファイル
  - When: `CheckerConfig.from_yaml(path)` を実行する
  - Then: エラーなく読み込まれ、既知フィールドのみが設定される

- AC-15-03: `--config` オプションでの CLI 連携
  - Given: `max_length: 5000` を含む YAML ファイルと `--config` オプション
  - When: `evaldataset <DATASET_ID> --config path/to/config.yaml` を実行する
  - Then: `TextLengthChecker` が 5,001 文字のテキストを WARNING として検出する

- AC-15-04: `skip_checkers` によるチェッカースキップ
  - Given: `skip_checkers: ["near_duplicate"]` の設定
  - When: チェックを実行する
  - Then: `NearDuplicateChecker` が実行されず、`Report` にそのチェッカーの結果が含まれない

---

## データフロー

```
DATASET_ID (CLI引数)
    ↓
loader.load_hf_dataset()
    ↓ Dataset
CheckerPipeline (best-effort: 1つの失敗で残りを止めない)
    ├─ SchemaChecker.check()         → CheckResult  ※ERROR時は後続テキスト系をスキップ
    ├─ MissingFieldChecker.check()   → CheckResult  ※欠損行を後続に伝播
    ├─ TextLengthChecker.check()     → CheckResult
    ├─ LanguageChecker.check()       → CheckResult
    ├─ HTMLChecker.check()           → CheckResult
    ├─ MojibakeChecker.check()       → CheckResult
    ├─ ExactDuplicateChecker.check() → CheckResult
    ├─ NearDuplicateChecker.check()  → CheckResult
    ├─ PiiChecker.check()            → CheckResult
    ├─ TokenLengthChecker.check()    → CheckResult
    └─ BoilerplateChecker.check()    → CheckResult
    ↓ Report
Reporter
    ├─ RichReporter (デフォルト、TTY接続時)
    └─ JsonReporter (--output json、またはTTY非接続時)
    ↓
[--fix 指定時] Fix パイプライン
    ├─ Step 1: TextCleaner（テキスト変換）
    │   ├─ MojibakeFix (ftfy)
    │   ├─ HtmlFix (BeautifulSoup)
    │   ├─ ControlCharFix (regex)
    │   └─ WhitespaceFix (regex)
    ├─ Step 2: チェッカー再実行（クリーニング後データに対して）
    └─ Step 3: RowFilter（問題行の除去）
        ├─ ExactDuplicateChecker → 重複行除去
        ├─ NearDuplicateChecker → 近似重複除去
        ├─ TextLengthChecker → 短文/長文除去
        └─ PiiChecker → PII含有行除去
    ↓ 修正・フィルタ済み Dataset
```

## 既知の制約・注意事項

- **日本語シングル**: `text_to_shingles()` は空白区切りで word-level shingle を生成するため、日本語テキストでは精度が低下する。将来的に文字 n-gram への切り替えを検討する
- **パフォーマンス**: 現行の Python ループベース行走査は 100 万行規模でボトルネックとなりうる。将来的に Arrow 列操作（`pa.compute`）への移行を検討する
- **トークナイザ**: `cl100k_base` は GPT-4 系トークナイザ。対象モデルに応じて `config.token_encoding` で切り替え可能
- **CJK mojibake**: `ftfy` は Unicode 正規化も行うため、一部の CJK 文字（半角カタカナ等）が「修正対象」と判定される場合がある
