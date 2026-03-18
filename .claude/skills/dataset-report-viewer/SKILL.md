---
name: dataset-report-viewer
description: データセット品質チェックレポートを閲覧・可視化する。evaldatasetの実行結果JSONを読み込み、サマリーや詳細を表示。「/dataset-report-viewer」で手動呼び出し、または「レポートを表示して」で起動。
---

# Dataset Report Viewer

evaldataset のチェック結果レポート（JSON）を読み込み、見やすく表示・可視化する。

## 使用ツール

- **Rich**: コンソール上でのテーブル・カラー表示
- **evaldataset --output json**: JSON形式のレポート出力

## ワークフロー

### 1. レポートファイルの特定

```bash
# 最新のレポートを検索
ls -lt *.json | head -5
```

または直接JSONファイルパスを指定。

### 2. レポートの読み込みと表示

```bash
# JSON形式で出力してから可視化
evaldataset username/my-dataset --output json > report.json

# レポート内容の確認
python -c "
import json
with open('report.json') as f:
    report = json.load(f)
print(json.dumps(report['summary'], indent=2))
"
```

### 3. 表示項目

| セクション | 内容 |
|-----------|------|
| サマリー | 総行数、Issue数、エラー/警告の内訳 |
| チェッカー別 | 各チェッカーの結果と検出Issue |
| 影響行リスト | 問題のある行のインデックスとサンプル |
| 統計 | テキスト長分布、言語分布、重複率等 |

### 4. 出力形式

- **コンソール**: Richテーブルで色付き表示
- **JSON**: 構造化データとしてそのまま出力

## 呼び出し方法

```
/dataset-report-viewer
```

または「レポートを表示して」「チェック結果を見せて」で起動。
