# 設計: ステップ1 コア基盤実装

## ファイル構成

すべてのロジックを `analyze.py` 1ファイルに集約（architecture.md の MVP 方針に従う）。

```
analyze.py
├── [インポート]
├── [定数] USAGE_PATTERNS
├── [Enum] RefType, UsageType
├── [dataclass] GrepRecord, ProcessStats
├── [モジュール変数] _ast_cache
├── [F-01] parse_grep_line(), process_grep_file()
├── [F-02] classify_usage(), classify_usage_regex(), get_ast()
├── [F-05] write_tsv()
├── [CLI] build_parser(), main()
└── if __name__ == "__main__": main()
```

## 主要設計判断

### ASTキャッシュ

```python
_ast_cache: dict[str, object | None] = {}
# None = javalangパースエラーが発生したファイル
```

モジュールレベルのdict。`get_ast()` 関数経由でアクセス。

### process_grep_file() での classify_usage() 呼び出し

第1段階（直接参照）の分類はこの関数内で実施。
GrepRecord を生成する際に usage_type を確定させる。

### main() の基本フロー（ステップ1版）

```
1. argparse でオプション解析
2. source_dir / input_dir の検証（存在・ディレクトリ確認）
3. input_dir/*.grep を検出
4. 各 .grep ファイルを process_grep_file() で処理
5. write_tsv() で出力
6. （IndirectTracker / GetterTracker は次ステップで追加）
```

### エンコーディング方針

- grep結果ファイル: `encoding='utf-8', errors='replace'`
- Javaソースファイル: `encoding='shift_jis', errors='replace'`
- TSV出力: `encoding='utf-8-sig'`（BOM付き）

### Windowsパス対応

```python
parts = re.split(r':(\d+):', line.rstrip(), maxsplit=1)
```

`C:\path\file.java:10:code` 形式に対応するため `maxsplit=1` を使用。
