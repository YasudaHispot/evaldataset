---
paths: "**/*.{ts,tsx,js,jsx,py,go,rs}"
---

# CLI入力バリデーション・ハードニングルール

エージェントはハルシネーションする。CLIの入力は公開WebAPIと同等の防御レベルで検証する。

## 必須実装

### ファイルパスの防御

- パストラバーサル（`../../`）を検出・拒否する
- `validate_safe_output_dir` を実装し、CWDにサンドボックスする
- パスを正規化（canonicalize）してからバリデーションする

```python
# 例
def validate_safe_output_dir(path: str, base_dir: str) -> str:
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(base_dir)):
        raise ValueError(f"Path escapes sandbox: {path}")
    return resolved
```

### 制御文字の拒否

- ASCII 0x20未満の不可視文字を含む入力を拒否する
- `reject_control_chars` バリデータを全テキスト入力に適用する

### リソースIDの検証

- `?` や `#` を含むリソースIDを拒否する（クエリパラメータ埋め込み防止）
- `%` を含む入力を拒否する（二重エンコード防止）
- HTTPレイヤーで `encode_path_segment` によるパーセントエンコーディングを行う

### JSON入力の受け入れ

- 個別フラグに加え `--json` でAPIペイロード全体をJSON入力可能にする
- フラグのフラットな名前空間ではネスト構造を表現できないため、生のJSONペイロードパスを提供する
- フラグとJSON入力の両方を同一バイナリでサポートする

## バリデーション対照表

| 攻撃ベクトル | エージェントの典型的ミス | 防御策 |
|---|---|---|
| ファイルパス | `../../.ssh` へのトラバーサル | 正規化+CWDサンドボックス |
| 制御文字 | 不可視ASCII生成 | 0x20未満を拒否 |
| リソースID | `fileId?fields=name` のようなパラメータ埋め込み | `?` `#` を拒否 |
| URLエンコード | 事前エンコード済み文字列の二重エンコード | `%` を拒否 |
| パスセグメント | 特殊文字生成 | HTTPレイヤーでパーセントエンコード |
