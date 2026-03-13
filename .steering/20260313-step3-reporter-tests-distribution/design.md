# 設計: ステップ3 仕上げ・テスト・配布

## F-06: Reporter

`main()` 末尾のインラインレポートを `print_report()` に切り出す。

```python
def print_report(stats: ProcessStats, processed_files: list[str]) -> None:
    """処理サマリを標準出力に出力する。"""
```

## test_analyze.py の構成

```
TestGrepParser         - parse_grep_line() の全パターン
TestUsageClassifier    - classify_usage_regex() の7種
TestTsvWriter          - write_tsv() のエンコード・ソート・ヘッダー
TestIndirectTracker    - determine_scope(), extract_variable_name()
TestIntegration        - フィクスチャを使ったE2Eフロー（直接参照）
```

## 統合テスト用フィクスチャ

```
tests/fixtures/
├── input/SAMPLE.grep          ← grep結果（直接参照パターンのみ）
├── java/Constants.java        ← static final定数のサンプル
└── expected/SAMPLE.tsv        ← 期待出力（手動作成）
```

統合テストはE2Eフロー確認のため、直接参照のみを対象にする（間接参照はJavaソースへの依存が深くなりすぎるため）。

## 配布ファイル設計

### run.sh
```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/analyze.py" "$@"
```

### setup.sh
```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m venv "$SCRIPT_DIR/.venv"
source "$SCRIPT_DIR/.venv/bin/activate"
pip install -r "$SCRIPT_DIR/requirements.txt"
echo "セットアップ完了。run.sh で実行してください。"
```

### Makefile ターゲット
- `test`: `python -m unittest discover`
- `lint`: `python -m flake8 analyze.py test_analyze.py`
- `package`: zip生成（dist/grep_analyzer.zip）
- `clean`: dist/ __pycache__ .venv 削除
