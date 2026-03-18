# evaldataset

HuggingFace CPT（Continued Pre-Training）用データセットの品質チェック・自動修正CLI。

## インストール

```bash
uv sync --dev
```

## 使い方

```bash
# 基本チェック
evaldataset username/my-dataset

# splitとテキストフィールド指定
evaldataset username/my-dataset --split train --text-field content

# 閾値カスタマイズ
evaldataset username/my-dataset --min-length 100 --languages en,ja

# 修正モード
evaldataset username/my-dataset --fix --fix-output ./cleaned_data

# サンプルチェック（大規模データセット用）
evaldataset username/my-dataset --sample-size 10000 --skip-duplicates

# ドライラン
evaldataset username/my-dataset --fix --dry-run

# JSON出力
evaldataset username/my-dataset --output json
```

## チェック項目

| カテゴリ | チェック内容 |
|---------|------------|
| 構造 | 欠損フィールド、スキーマ検証 |
| テキスト品質 | 短文/長文、HTML残留、制御文字、空白、URL密度、定型文 |
| 重複 | 完全一致（SHA-256）、近似重複（MinHash LSH） |
| コンテンツ | 言語検出、PII検出、トークン長 |

## 開発

```bash
# テスト実行
uv run pytest

# カバレッジ付き
uv run pytest --cov=evaldataset --cov-report=term-missing
```

## .claude/rules/

CLI を実装する際に Claude Code が参照するルールファイル群。

### 出典

- **CLI 設計ルールの原典**
  [You Need to Rewrite Your CLI for AI Agents](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/) — Justin Poehnelt

- **ルールファイルのディレクトリ構成**
  [Claude Code の .claude/rules/ を活用して CLAUDE.md の肥大化を防ぐ](https://qiita.com/tomada/items/cb05d3a7aa00cb35c486) — @tomada
