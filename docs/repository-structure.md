# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
grep_analyzer/
├── analyze.py           # エントリーポイント（全ロジック）
├── test_analyze.py      # unittestによる単体テスト
├── requirements.txt     # 依存ライブラリ（javalang のみ）
├── setup.sh             # venv作成スクリプト（Unix/Mac）
├── setup.bat            # venv作成スクリプト（Windows）
├── run.sh               # 実行ラッパー（Unix/Mac）
├── run.bat              # 実行ラッパー（Windows）
├── Makefile             # `make package` でdist/grep_analyzer.zipを生成
├── README.txt           # 利用者向け手順書（日本語）
├── input/               # grep結果ファイルの配置ディレクトリ
│   └── .gitkeep
├── output/              # TSV出力先ディレクトリ（自動作成）
│   └── .gitkeep
└── docs/                # プロジェクトドキュメント
    ├── ideas/
    │   └── initial-requirements.md
    ├── product-requirements.md
    ├── functional-design.md
    ├── architecture.md
    ├── repository-structure.md  （本ドキュメント）
    ├── development-guidelines.md
    └── glossary.md
```

## ディレクトリ詳細

### analyze.py（メインスクリプト）

**役割**: ツールの全ロジックを1ファイルに集約したエントリーポイント

**配置クラス・関数**:
- `GrepRecord`（dataclass）: 分析結果の1件を表すデータモデル
- `ProcessStats`（dataclass）: 処理統計（スキップ・フォールバック件数）
- `RefType`（Enum）: 参照種別（直接/間接/間接（getter経由））
- `UsageType`（Enum）: 使用タイプ（7種）
- `parse_grep_line()`: grep結果1行のパース
- `process_grep_file()`: grepファイル全行の処理（第1段階）
- `classify_usage()`: AST + 正規表現フォールバックによる分類
- `classify_usage_regex()`: 正規表現フォールバック
- `track_constant()`: 定数のプロジェクト全体追跡（第2段階）
- `track_field()`: フィールドの同一クラス追跡（第2段階）
- `track_local()`: ローカル変数の同一メソッド追跡（第2段階）
- `find_getter_names()`: getter候補の特定（第3段階）
- `track_getter_calls()`: getter呼び出し箇所の追跡（第3段階）
- `write_tsv()`: UTF-8 BOM付きTSV出力
- `print_report()`: 処理サマリの標準出力表示
- `main()`: エントリーポイント（argparse + 全処理の統括）

**命名規則**:
- 関数: `snake_case`、動詞で始める
- クラス: `PascalCase`
- 定数: `UPPER_SNAKE_CASE`（例: `USAGE_PATTERNS`）
- Boolean変数: `is_`/`has_`/`should_` で始める

**依存関係**:
- 依存可能: `re`, `csv`, `argparse`, `pathlib`, `sys`, `dataclasses`, `enum`, `javalang`
- 依存禁止: その他の外部ライブラリ

---

### test_analyze.py（テストファイル）

**役割**: `analyze.py` のユニットテスト

**構造**:
```
test_analyze.py
├── class TestGrepParser(unittest.TestCase)
│   ├── test_parse_valid_line_returns_dict
│   ├── test_parse_binary_notice_line_returns_none
│   ├── test_parse_empty_line_returns_none
│   └── test_parse_windows_path_handled
├── class TestUsageClassifier(unittest.TestCase)
│   ├── test_classify_annotation
│   ├── test_classify_constant_definition
│   ├── test_classify_variable_assignment
│   ├── test_classify_condition
│   ├── test_classify_return
│   ├── test_classify_method_argument
│   └── test_classify_other
├── class TestTsvWriter(unittest.TestCase)
│   ├── test_write_tsv_creates_file
│   ├── test_write_tsv_utf8_bom_encoding
│   ├── test_write_tsv_sort_order
│   └── test_write_tsv_header_columns
└── class TestIntegration(unittest.TestCase)
    └── test_full_flow_produces_expected_records
```

**命名規則**:
- パターン: `test_[対象関数]_[条件]_[期待結果]`
- 例: `test_parse_valid_line_returns_dict`

---

### input/ および output/

**役割**:
- `input/`: ユーザーが `grep -rn "文言" /java > input/文言.grep` で配置する
- `output/`: ツールが `analyze.py` 実行時に自動作成・TSVを書き出す

**ファイル命名規則**:
- 入力: `[文言].grep`（拡張子は `.grep`）
- 出力: `[文言].tsv`（入力ファイル名と対応）

**例**:
```
input/
├── .gitkeep
├── ERROR_CODE.grep    # "ERROR_CODE" を grep した結果
└── STATUS_OK.grep     # "STATUS_OK" を grep した結果

output/
├── .gitkeep
├── ERROR_CODE.tsv     # ERROR_CODE の分析結果
└── STATUS_OK.tsv      # STATUS_OK の分析結果
```

---

### docs/（ドキュメントディレクトリ）

**配置ドキュメント**:
- `product-requirements.md`: プロダクト要求定義書（PRD）
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書（本ドキュメントの姉妹ドキュメント）
- `repository-structure.md`: リポジトリ構造定義書（本ドキュメント）
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

---

### setup.sh / setup.bat（セットアップスクリプト）

**役割**: Python仮想環境（venv）の作成と依存ライブラリのインストール

**setup.sh（Unix/Mac）の内容イメージ**:
```bash
#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "セットアップ完了。run.sh で実行してください。"
```

**setup.bat（Windows）の内容イメージ**:
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
echo セットアップ完了。run.bat で実行してください。
```

---

### run.sh / run.bat（実行ラッパー）

**役割**: venv を有効化して `analyze.py` を実行する

**run.sh（Unix/Mac）の内容イメージ**:
```bash
#!/bin/bash
source .venv/bin/activate
python analyze.py "$@"
```

**run.bat（Windows）の内容イメージ**:
```bat
.venv\Scripts\activate
python analyze.py %*
```

---

### Makefile（パッケージング）

**役割**: `make package` で配布用zipを生成する

**ターゲット**:
```makefile
package:
    mkdir -p dist
    zip -r dist/grep_analyzer.zip analyze.py test_analyze.py \
        requirements.txt setup.sh setup.bat run.sh run.bat \
        README.txt input/.gitkeep output/.gitkeep

test:
    python -m unittest discover

clean:
    rm -rf dist/ __pycache__/ .venv/
```

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| メインスクリプト | プロジェクトルート | `snake_case.py` | `analyze.py` |
| テストファイル | プロジェクトルート | `test_[対象].py` | `test_analyze.py` |
| 実行スクリプト | プロジェクトルート | `run.sh` / `run.bat` | - |
| セットアップ | プロジェクトルート | `setup.sh` / `setup.bat` | - |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | プロジェクトルート | `test_[対象モジュール].py` | `test_analyze.py` |

### 設定ファイル

| ファイル種別 | 配置先 | 命名規則 |
|------------|--------|---------|
| 依存ライブラリ | プロジェクトルート | `requirements.txt` |
| Python仮想環境 | プロジェクトルート | `.venv/`（gitignore対象） |
| Make設定 | プロジェクトルート | `Makefile` |

## 命名規則

### ファイル名

- **Pythonスクリプト**: `snake_case.py`
  - 例: `analyze.py`, `test_analyze.py`
- **シェルスクリプト**: `snake_case.sh`
  - 例: `run.sh`, `setup.sh`

### Pythonコード内

- **関数・変数**: `snake_case`
  - 例: `parse_grep_line`, `ast_cache`, `source_dir`
- **クラス**: `PascalCase`
  - 例: `GrepRecord`, `ProcessStats`, `UsageType`
- **定数**: `UPPER_SNAKE_CASE`
  - 例: `USAGE_PATTERNS`, `DEFAULT_ENCODING`
- **プライベート変数**: `_snake_case`（モジュールレベルキャッシュ等）
  - 例: `_ast_cache`

## 依存関係のルール

```
analyze.py (エントリーポイント)
    ↓ (import)
re, csv, argparse, pathlib, sys, dataclasses, enum  # 標準ライブラリ
    ↓ (import)
javalang  # 唯一の外部依存
```

**禁止される依存**:
- `test_analyze.py` → `analyze.py` 以外のモジュール（外部ライブラリのみ）
- 新しい外部ライブラリの追加（原則として `javalang` のみ）

## スケーリング戦略

### 機能の追加

新しい機能を追加する際の配置方針:

1. **小規模機能**: `analyze.py` に関数を追加
2. **中規模機能（Post-MVP）**: `src/` パッケージを作成してモジュール分割
3. **大規模機能**: サブパッケージとして分離

**Post-MVP でのパッケージ分割例**:
```
grep_analyzer/
├── analyze.py           # エントリーポイント（薄いラッパーに変更）
├── src/
│   ├── __init__.py
│   ├── models.py        # GrepRecord, ProcessStats, Enum
│   ├── parser.py        # GrepParser (F-01)
│   ├── classifier.py    # UsageClassifier (F-02)
│   ├── tracker.py       # IndirectTracker (F-03)
│   ├── getter_tracker.py # GetterTracker (F-04)
│   └── writer.py        # TsvWriter (F-05) + Reporter (F-06)
└── tests/
    ├── test_parser.py
    ├── test_classifier.py
    └── test_tracker.py
```

### ファイルサイズの管理

**分割の目安**:
- `analyze.py` が500行を超えた場合: `src/` パッケージへの分割を検討
- 1機能（F-01〜F-06）が300行を超えた場合: 独立モジュールへの分離を検討

## 特殊ディレクトリ

### .steering/（ステアリングファイル）

**役割**: 特定の開発作業における「今回何をするか」を定義

**構造**:
```
.steering/
└── [YYYYMMDD]-[task-name]/
    ├── requirements.md      # 今回の作業の要求内容
    ├── design.md            # 変更内容の設計
    └── tasklist.md          # タスクリスト
```

**命名規則**: `20250115-implement-f01-grep-parser` 形式

### .claude/（Claude Code設定）

**役割**: Claude Code設定とカスタマイズ

**構造**:
```
.claude/
├── commands/                # スラッシュコマンド
├── skills/                  # タスクモード別スキル
└── agents/                  # サブエージェント定義
```

## 除外設定

### .gitignore

プロジェクトで除外すべきファイル:
- `.venv/`（仮想環境）
- `__pycache__/`
- `*.pyc` / `*.pyo`
- `dist/`（パッケージング成果物）
- `*.egg-info/`
- `.env`
- `*.log`
- `.DS_Store`
- `output/*.tsv`（生成物。必要に応じてコミット対象に変更）

### コード品質ツール（flake8等）

ツールで除外すべきディレクトリ:
- `.venv/`
- `__pycache__/`
- `.steering/`
- `dist/`
