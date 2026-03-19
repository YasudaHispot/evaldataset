---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.py"
  - "**/*.go"
  - "**/*.rs"
  - "docs/requirements.md"
  - "docs/design.md"
---

# CLI出力フォーマットルール

CLIの出力は人間とAIエージェント両方が消費する。エージェントはJSON以外の出力を正確にパースできない。

## 必須実装

### 構造化出力の提供

- `--output json` フラグ（または `-o json`）を必ず実装する
- 環境変数 `OUTPUT_FORMAT=json` でもJSON出力に切り替え可能にする
- stdoutがTTYでない場合はデフォルトでJSON（NDJSON）出力にする

```bash
# 判定例
if [ -t 1 ]; then
  # 人間向け整形出力
else
  # NDJSON出力
fi
```

### NDJSON対応

- ページネーション結果は `--page-all` でNDJSON（1行1JSONオブジェクト）出力する
- トップレベル配列のバッファリングを避け、ストリーム処理を可能にする
- 各行が独立した有効なJSONであること

### 出力の一貫性

- エラーもJSON形式で出力する（`--output json` 時）
- exitコードを正しく設定する（成功: 0、入力エラー: 1、実行エラー: 2）
- 人間向けメッセージはstderrに、データはstdoutに分離する
