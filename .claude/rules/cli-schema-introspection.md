---
paths: "**/*.{ts,tsx,js,jsx,py,go,rs}"
---

# CLIスキーマ自己記述ルール

エージェントは外部ドキュメントを効率的に参照できない。CLI自体が自身のAPIの正規情報源（canonical truth source）であるべき。

## 必須実装

### ランタイムスキーマ出力

- `<command> schema <subcommand>` または `<command> --describe` で、コマンドのスキーマをJSON形式で出力する
- スキーマには以下を含める:
  - パラメータ名・型・必須/任意
  - リクエストボディの構造
  - レスポンスの型定義
  - 必要な認証スコープ（該当する場合）

```bash
# 使用例
mycli schema users.list
# → JSON Schemaが出力される
```

### ヘルプの構造化

- `--help --json` で構造化されたヘルプをJSON出力可能にする
- REST APIでなくても `--describe` は有効。全CLIに適用できる
- エージェントがトークンを消費せずにコマンド仕様を取得できるようにする
