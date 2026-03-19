# evaldataset 設計書

## 概要

HuggingFace CPT（Continued Pre-Training）用データセットの品質チェック・自動修正を行うPython CLIアプリケーション。

## アーキテクチャ

### データフロー

```
CLI → DatasetLoader → Checkers(並列) → ReportBuilder → Console/JSON出力
                                                    ↓
                                              [--fix時]
                                           FixerPipeline → 修正済みデータ保存
```

### プロジェクト構造

```
src/evaldataset/
├── __init__.py
├── cli.py                    # Click CLI エントリポイント
├── config.py                 # CheckerConfig dataclass
├── loader.py                 # HuggingFaceデータセット読み込み
├── models.py                 # Issue, CheckResult, Report
├── checks/
│   ├── __init__.py
│   ├── base.py              # BaseChecker ABC
│   ├── registry.py          # チェッカー登録・発見
│   ├── structural.py        # 構造チェック（欠損、スキーマ）
│   ├── text_quality.py      # テキスト品質（HTML, 空白, 文字化け, URL等）
│   ├── duplicates.py        # 完全一致・近似重複検出
│   └── content.py           # 言語検出, PII, トークン長
├── fixers/
│   ├── __init__.py
│   ├── base.py              # BaseFixer ABC
│   ├── text_fixer.py        # テキスト変換（HTML除去, 正規化等）
│   ├── filter_fixer.py      # 行フィルタ（重複除去, 長さフィルタ等）
│   └── pipeline.py          # Fixer実行パイプライン
├── report/
│   ├── __init__.py
│   ├── builder.py           # CheckResult集約→Report
│   ├── json_report.py       # JSON出力
│   └── console_report.py    # Richコンソール出力
└── utils/
    ├── __init__.py
    ├── text.py              # テキストユーティリティ
    ├── hashing.py           # MinHash/SimHashヘルパー
    └── pii.py               # PII正規表現パターン
```

## 依存ライブラリ

| ライブラリ | 用途 |
|-----------|------|
| datasets | HuggingFaceデータセット読み込み |
| click | CLI フレームワーク |
| rich + tqdm | コンソール出力・プログレスバー |
| datasketch | MinHash近似重複検出 |
| ftlangdetect | 高速言語検出 |
| beautifulsoup4 | HTMLタグ除去 |
| ftfy | 文字化け(mojibake)修正 |
| regex | Unicode対応正規表現 |
| tiktoken | トークン数カウント |
| pyyaml | 設定ファイル読み込み |

## データモデル

### Issue

チェッカーが検出した個別の品質問題。

| フィールド | 型 | 説明 |
|-----------|------|------|
| checker | str | 検出したチェッカー名 |
| severity | Severity | error / warning / info |
| message | str | 問題の説明 |
| row_indices | list[int] | 該当行のインデックス |
| details | dict[str, Any] | チェッカー固有の詳細情報 |

### CheckResult

1つのチェッカーの実行結果。

| フィールド | 型 | 説明 |
|-----------|------|------|
| checker_name | str | チェッカー名 |
| issues | list[Issue] | 検出されたIssueリスト |
| stats | dict[str, Any] | 統計情報（行数、比率等） |

### Report

全チェッカーの結果を集約したレポート。

| フィールド | 型 | 説明 |
|-----------|------|------|
| dataset_id | str | HuggingFaceデータセットID |
| split | str | 対象split名 |
| total_rows | int | 総行数 |
| text_field | str | テキストフィールド名 |
| results | list[CheckResult] | 各チェッカーの結果 |

## Checker設計

### 基底クラス

```python
class BaseChecker(ABC):
    name: str = ""

    def __init__(self, config: CheckerConfig) -> None:
        self.config = config

    @abstractmethod
    def check(self, dataset: Dataset, text_field: str) -> CheckResult: ...
```

### レジストリ

`@register` デコレータでクラス定義時に自動登録される。

```python
@register
class MissingFieldChecker(BaseChecker):
    name = "missing_field"
    ...
```

### チェック項目一覧

#### 構造チェック (structural.py)

| チェッカー | 説明 | Severity |
|-----------|------|----------|
| MissingFieldChecker | text_fieldがNone/空の行検出 | error |
| SchemaChecker | フィールド存在・型検証 | error/warning |

#### テキスト品質 (text_quality.py)

| チェッカー | 説明 | Severity |
|-----------|------|----------|
| ShortTextChecker | 短すぎ/長すぎテキスト（configurable閾値） | warning |
| HtmlResidueChecker | HTMLタグ残留 | warning |
| ControlCharChecker | 制御文字・文字化け検出（ftfy） | warning |
| WhitespaceChecker | 過度な空白・改行 | warning |
| UrlEmailDensityChecker | URL/メール密度が閾値超過 | warning |
| BoilerplateChecker | 定型文パターン（copyright, cookie等） | info |

#### 重複検出 (duplicates.py)

| チェッカー | 説明 | Severity |
|-----------|------|----------|
| ExactDuplicateChecker | SHA-256ハッシュ完全一致 | warning |
| NearDuplicateChecker | MinHash LSH（Jaccard >= 0.8） | warning |

#### コンテンツ品質 (content.py)

| チェッカー | 説明 | Severity |
|-----------|------|----------|
| LanguageChecker | 言語検出（ftlangdetect） | warning |
| PiiChecker | PII正規表現検出（email, 電話, SSN等） | error |
| TokenLengthChecker | トークン長分布・外れ値検出 | info |

## Fixer設計

### 基底クラス

```python
class BaseFixer(ABC):
    name: str = ""

    @abstractmethod
    def fix(self, dataset: Dataset, text_field: str, report: Report) -> Dataset: ...
```

### 実行順序

1. **フィルタ系**（行削除）を先に実行
   - 重複除去
   - 長さフィルタ
   - 欠損行除去
2. **変換系**（テキスト変更）を後に実行
   - HTML除去
   - 空白正規化
   - 文字化け修正

### 設計原則

- `dataset.map()` / `dataset.filter()` でArrow形式を維持（メモリ効率）
- `--dry-run` で実際の変更を行わず、適用予定の修正をレポートする

## CLI インターフェース

```
evaldataset DATASET_ID [OPTIONS]
```

### 引数・オプション

| 引数/オプション | 型 | デフォルト | 説明 |
|----------------|------|-----------|------|
| DATASET_ID | str | (必須) | HuggingFaceデータセットID |
| --split | str | train | 対象split |
| --text-field | str | text | テキストフィールド名 |
| --config | path | - | YAML設定ファイルパス |
| --min-length | int | 50 | 最小テキスト長 |
| --max-length | int | 100000 | 最大テキスト長 |
| --languages | str | en | 許可する言語（カンマ区切り） |
| --sample-size | int | - | サンプル数（大規模データセット用） |
| --skip-duplicates | flag | false | 重複検出をスキップ |
| --fix | flag | false | 修正モード |
| --fix-output | path | - | 修正済みデータの出力先 |
| --dry-run | flag | false | 修正のドライラン |
| --output | str | console | 出力形式（console / json） |
| --fields | str | - | 出力フィールド制限 |

### Exit コード

| コード | 意味 |
|-------|------|
| 0 | チェック完了、問題なし |
| 1 | チェック完了、問題あり |
| 2 | 実行エラー（データセット読み込み失敗等） |

## 設定ファイル (configs/default.yaml)

```yaml
min_length: 50
max_length: 100000
languages:
  - en
language_threshold: 0.5
minhash_threshold: 0.8
minhash_num_perm: 128
max_url_density: 0.1
max_email_density: 0.05
token_encoding: cl100k_base
max_token_length: 8192
detect_pii: true
boilerplate_patterns:
  - "(?i)^copyright\\s"
  - "(?i)^all rights reserved"
  - "(?i)cookie\\s*(policy|notice|consent)"
  - "(?i)privacy\\s*policy"
  - "(?i)terms\\s*(of|and)\\s*(service|use|conditions)"
  - "(?i)subscribe\\s+to\\s+(our|the)\\s+newsletter"
```

## 実装フェーズ

### Phase 1: 基盤
- pyproject.toml, .gitignore
- models.py, config.py, loader.py
- checks/base.py, checks/registry.py
- cli.py（最小CLI）

### Phase 2: コアチェック
- checks/structural.py
- checks/text_quality.py + utils/text.py
- utils/pii.py + checks/content.py

### Phase 3: 重複検出
- utils/hashing.py + checks/duplicates.py

### Phase 4: レポート
- report/builder.py, json_report.py, console_report.py
- CLIにレポート統合

### Phase 5: 修正モード
- fixers/base.py
- fixers/text_fixer.py, filter_fixer.py
- fixers/pipeline.py
- CLIに--fixモード統合

### Phase 6: 仕上げ
- configs/default.yaml
- エッジケース対応、エラーハンドリング
