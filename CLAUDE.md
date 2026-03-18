# CLAUDE.md

このファイルはClaude Codeがこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

HuggingFace CPT（Continued Pre-Training）用データセットの品質チェック・自動修正を行うPython CLIアプリケーション。

## 最重要事項

- GitHubフロー
- `docs/`のドキュメントを参照
- TDD（テスト駆動開発）
- pytest による単体テスト、カバレッジ計測
- パッケージ管理は uv を使用

## 技術スタック

- Python 3.11+
- Click（CLIフレームワーク）
- datasets（HuggingFace）
- Rich（コンソール出力）
- pytest + pytest-cov（テスト・カバレッジ）

## コマンド

```bash
# セットアップ
uv sync --dev

# テスト実行
uv run pytest

# カバレッジ付きテスト
uv run pytest --cov=evaldataset --cov-report=term-missing

# CLI実行
uv run evaldataset <DATASET_ID> [OPTIONS]
```

## プロジェクト構造

- `src/evaldataset/` - メインソースコード
- `tests/` - テストコード
- `configs/` - 設定ファイル
- `docs/` - ドキュメント
