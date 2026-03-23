# evaldataset

HuggingFace CPT（Continued Pre-Training）用データセットの品質チェック・自動修正CLI。

## インストール

```bash
# 開発用（テスト含む）
uv sync --dev

# 依存のみ
uv sync
```

## 使い方

### 基本

```bash
# HuggingFace Hub のデータセットをチェック
evaldataset username/my-dataset

# ローカルの Parquet ディレクトリをチェック
evaldataset /path/to/parquet_dir
```

### インストールせずに実行

```bash
# uv run 経由で直接実行（uv sync 不要）
uvx --from . evaldataset username/my-dataset

# リポジトリ内から実行
uv run evaldataset username/my-dataset

# リポジトリ外から GitHub を指定して実行
uvx --from git+https://github.com/YasudaHispot/evaldataset evaldataset username/my-dataset
```

### 出力形式

```bash
# Rich テーブル形式（デフォルト、TTY接続時）
evaldataset username/my-dataset

# JSON 出力
evaldataset username/my-dataset --output json

# パイプ時は自動で JSON に切り替わる
evaldataset username/my-dataset | jq '.summary'
```

### チェック対象の制御

```bash
# split とテキストフィールドを指定
evaldataset username/my-dataset --split validation --text-field content

# 大規模データセットをサンプリング
evaldataset username/my-dataset --sample-size 10000

# 特定チェッカーをスキップ（複数指定可）
evaldataset username/my-dataset --skip-checker near_duplicate --skip-checker pii
```

### YAML 設定ファイル

```bash
evaldataset username/my-dataset --config config.yaml
```

```yaml
# config.yaml
min_length: 100
max_length: 50000
languages:
  - en
  - ja
minhash_threshold: 0.9
skip_checkers:
  - near_duplicate
```

設定マージの優先順位: CLI オプション > YAML > デフォルト値

### 自動修正

```bash
# 修正を実行して出力
evaldataset username/my-dataset --fix --fix-output ./cleaned_data

# ドライラン（修正対象の確認のみ、ファイル書き込みなし）
evaldataset username/my-dataset --fix --dry-run
```

`--fix` で実行されるクリーニング:

| 修正内容 | 対応状況 |
|---------|---------|
| 文字化け修復 (ftfy) | 対応済み |
| HTML タグ除去 | 対応済み |
| 制御文字除去 | 対応済み |
| 空白正規化 | 対応済み |
| 完全一致重複の除去 | 未実装 |
| 近似重複の除去 | 未実装 |
| 短文/長文のフィルタリング | 未実装 |
| PII を含む行の除去 | 未実装 |

## CLIオプション一覧

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `DATASET_ID` (引数) | 必須 | HuggingFace Hub ID またはローカルディレクトリパス |
| `--split` | `train` | 対象スプリット |
| `--text-field` | `text` | テキストフィールド名 |
| `--config` | なし | YAML 設定ファイルパス |
| `--output` | `rich` | 出力形式 (`rich` / `json`) |
| `--fix` | `False` | 自動修正を実行する |
| `--fix-output` | なし | 修正済み Dataset の出力先 |
| `--sample-size` | なし | サンプリング件数 |
| `--skip-checker` | なし | スキップするチェッカー名（複数指定可） |
| `--dry-run` | `False` | 変更なしで修正対象を確認する |

## 終了コード

| コード | 意味 |
|-------|------|
| 0 | 品質問題なし |
| 1 | WARNING が検出された |
| 2 | ERROR が検出された |
| 3 | 実行エラー（データセット読み込み失敗等） |

## チェック項目

| カテゴリ | チェッカー名 | チェック内容 |
|---------|------------|------------|
| 構造 | `missing_field` | 欠損・空フィールド |
| テキスト品質 | `text_length` | 短文/長文検出 |
| テキスト品質 | `html` | HTML タグ残留 |
| テキスト品質 | `mojibake` | 文字化け検出 |
| テキスト品質 | `boilerplate` | 定型文・URL高密度テキスト |
| 重複 | `exact_duplicate` | 完全一致（SHA-256） |
| 重複 | `near_duplicate` | 近似重複（MinHash LSH） |
| コンテンツ | `language` | 言語検出 |
| コンテンツ | `pii` | PII（個人情報）検出 |
| コンテンツ | `token_length` | トークン数上限チェック |

## 設定パラメータ

| キー | デフォルト | 説明 |
|-----|-----------|------|
| `min_length` | `50` | テキスト最小文字数 |
| `max_length` | `100000` | テキスト最大文字数 |
| `languages` | `["en"]` | 許可言語コードリスト |
| `language_threshold` | `0.5` | 言語検出信頼度閾値 |
| `minhash_threshold` | `0.8` | 近似重複の類似度閾値 |
| `minhash_num_perm` | `128` | MinHash 置換数 |
| `skip_duplicates` | `False` | 重複チェックのスキップ |
| `max_url_density` | `0.1` | URL 文字密度の上限 |
| `max_email_density` | `0.05` | Email 文字密度の上限 |
| `token_encoding` | `"cl100k_base"` | tiktoken エンコーディング名 |
| `max_token_length` | `8192` | トークン数の上限 |
| `detect_pii` | `True` | PII 検出の有効フラグ |
| `skip_checkers` | `[]` | スキップするチェッカー名リスト |

## 開発

```bash
# テスト実行
uv run pytest

# カバレッジ付き
uv run pytest --cov=evaldataset --cov-report=term-missing

# ユニットテストのみ
uv run pytest tests/unit/ -v

# 結合テストのみ
uv run pytest tests/integration/ -v
```
