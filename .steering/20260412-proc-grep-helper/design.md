# 設計書

## アーキテクチャ概要

Javaツール（`analyze.py`）と同じ**パイプラインアーキテクチャ**を採用する。
ファイルは `analyze_proc.py` として独立して作成する（案B: 言語別独立）。

```
┌─────────────────────────────┐
│   入力レイヤー               │ ← argparse + GrepParser（Javaと同一ロジック）
│   (CLIパース・ファイル読込)  │   grep結果ファイルを読み込み
├─────────────────────────────┤
│   分析レイヤー               │ ← 2段階（Pro*CはJavaの第3段階なし）
│   (正規表現分類・参照追跡)  │   第1段階: ProcUsageClassifier（直接参照の分類）
│                             │   第2段階: ProcIndirectTracker（間接参照の追跡）
├─────────────────────────────┤
│   出力レイヤー               │ ← TsvWriter + Reporter（Javaと同一ロジック）
│   (TSV出力・レポート)       │   結果をTSVに書き出しレポート表示
└─────────────────────────────┘
```

**Javaツールとの主な相違点**:
- 第3段階（GetterTracker）なし
- AST解析なし → 正規表現が本線（フォールバックではなく主体）
- 対象ファイル: `.pc`, `.h`
- 使用タイプ: Java 7種 → Pro*C 7種（内容が異なる）

## コンポーネント設計

### 1. GrepParser（Javaツールと同一）

**責務**: `input/*.grep` の読み込み・パース・スキップ処理

**実装の要点**:
- `analyze.py` の `parse_grep_line()` / `process_grep_file()` と同一ロジック
- grep結果ファイルのエンコーディング: `encoding='cp932', errors='replace'`
- Pro*Cソースファイルのエンコーディング: `encoding='shift_jis', errors='replace'`（日本語コメントが多いため）

---

### 2. ProcUsageClassifier（Pro*C向け使用タイプ分類器）

**責務**: コード行を正規表現で7種の使用タイプに分類する

**使用タイプ一覧（優先度順）**:

```python
PROC_USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bEXEC\s+SQL\b', re.IGNORECASE),              "EXEC SQL文"),
    (re.compile(r'^\s*#\s*define\b'),                            "#define定数定義"),
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\bstrcmp\s*\(|[!=]='), "条件判定"),
    (re.compile(r'\breturn\b'),                                   "return文"),
    (re.compile(r'\b\w[\w\s\*\[\]]*\s+\w+\s*[=;]'),            "変数代入"),
    (re.compile(r'\w+\s*\('),                                    "関数引数"),
]
# 非マッチ → "その他"
```

**EXEC SQL文の細分類（`usage_type` の補足情報として `code` に残る）**:
- SELECT / INSERT / UPDATE / DELETE / OPEN / FETCH / CLOSE / COMMIT / ROLLBACK 等
- 分類は `code` 列の目視で判断可能なため、`usage_type` での細分類はしない

---

### 3. ProcIndirectTracker（間接参照追跡器）

**責務**: 直接参照の種類に応じて間接的な使用箇所を追跡する

#### 3-1. #define定数追跡（プロジェクト全体）

```
#define NAME "keyword"  ← 直接参照（#define定数定義）
    ↓
プロジェクト全体の .pc / .h ファイルをgrep → NAME が使われている行を収集
    ↓
各行を ProcUsageClassifier で分類 → GrepRecord（ref_type=間接）として記録
```

**定数名抽出パターン**:
```python
re.match(r'^\s*#\s*define\s+(\w+)\s+', code)
# → group(1) が定数名
```

#### 3-2. ローカル変数追跡（同一関数スコープ内）

```
char localVar[] = "keyword";  ← 直接参照（変数代入）
    ↓
同一ファイル内で関数スコープ（{ } の対応）を特定
    ↓
スコープ内で localVar が使われている行を収集
    ↓
各行を ProcUsageClassifier で分類
```

**関数スコープ特定**:
- 直接参照の行番号から上方向に `{` を走査して関数先頭を探す
- `{` `}` のネスト深度を追跡して関数の終端を特定
- 正規表現でのヒューリスティック（完全なCパーサではない）

#### 3-3. ホスト変数追跡（同一ファイル内）

```
EXEC SQL BEGIN DECLARE SECTION;
    char hostVar[256];  ← 直接参照（ホスト変数宣言）
EXEC SQL END DECLARE SECTION;
    ↓
同一ファイル全体で :hostVar が使われている行を収集
（Pro*Cホスト変数はコロン付き `:hostVar` でSQL内で参照される）
    ↓
各行を ProcUsageClassifier で分類
```

**ホスト変数参照パターン**:
```python
re.compile(r':\b' + re.escape(var_name) + r'\b')
```

**ホスト変数宣言の検出**:
- DECLARE SECTION内であることの判定はステートフルなスキャンで行う
- `EXEC SQL BEGIN DECLARE SECTION` ～ `EXEC SQL END DECLARE SECTION` の間の変数宣言行を対象とする

---

### 4. TsvWriter（Javaツールと同一）

**責務**: GrepRecordリストをUTF-8 BOM付きTSVに書き出す

- `analyze.py` の `write_tsv()` と同一ロジック
- ソート: `(keyword, filepath, int(lineno))`

---

### 5. Reporter（Javaツールと同一）

**責務**: 処理サマリを標準出力に表示する

---

### 6. CLI / エントリポイント

**ファイル**: `analyze_proc.py`
**実行スクリプト**: `run_proc.sh` / `run_proc.bat`

```bash
python analyze_proc.py --source-dir /path/to/proc_project
```

`run_proc.sh` は `run.sh` と同一構造で作成する。

## データフロー

### メインフロー（UC-01）

```
1. argparse で --source-dir / --input-dir / --output-dir を取得
2. input/*.grep を全件検出
3. 各.grepファイルに対して:
   a. GrepParser で全行をパース → 直接参照レコードリスト
   b. ProcUsageClassifier で各レコードの usage_type を設定
   c. ProcIndirectTracker で間接参照レコードを生成
      - #define定数定義 → プロジェクト全体追跡
      - 変数代入 → スコープ判定して追跡
      - ホスト変数宣言 → 同一ファイル追跡
   d. 直接参照 + 間接参照レコードをまとめて TsvWriter で出力
4. Reporter で処理サマリを表示
```

## エラーハンドリング戦略

Javaツールと同一方針:

| エラー種別 | 処理 |
|---|---|
| `--source-dir` 不在 | exit code 1 / stderr |
| `input/` が空 | exit code 1 / stderr |
| ファイル読み込みエラー | `errors='replace'` で継続、レポートに記録 |
| 正規表現スキップ | 「その他」として出力（スキップしない） |

## テスト戦略

### ユニットテスト（`test_analyze_proc.py`）

- `parse_grep_line()`: 正常行・バイナリ通知行・空行・不正フォーマット行
- `classify_usage_proc()`: 7種の使用タイプのサンプルコード
- `extract_define_name()`: `#define NAME "value"` からNAMEを抽出
- `extract_variable_name_proc()`: 変数宣言行から変数名を抽出
- `write_tsv()`: 出力ファイルの列数・エンコード・ソート順

### 統合テスト（`tests/proc/`）

- サンプル `.pc` / `.h` ファイル群 + サンプルgrep結果を用いたE2Eフロー
- 直接参照・#define間接参照・ホスト変数間接参照が全て正しくTSVに出力されること

## 依存ライブラリ

新規追加ライブラリなし。標準ライブラリ（`re`, `csv`, `pathlib`, `argparse`）のみ。

## ディレクトリ構造

```
analyze_proc.py          # Pro*C分析ツール（新規作成）
run_proc.sh              # Unix実行スクリプト（新規作成）
run_proc.bat             # Windows実行スクリプト（新規作成）
test_analyze_proc.py     # ユニットテスト（新規作成）
tests/
└── proc/
    ├── input/
    │   └── sample.grep  # テスト用grep結果
    ├── src/
    │   ├── sample.pc    # テスト用Pro*Cソース
    │   └── constants.h  # テスト用ヘッダ
    └── expected/
        └── sample.tsv   # 期待TSV
```

## 実装の順序

1. データモデル・定数定義（GrepRecord, ProcessStats, 使用タイプ定数）
2. GrepParser（parse_grep_line, process_grep_file）
3. ProcUsageClassifier（classify_usage_proc）
4. ProcIndirectTracker（extract_define_name, track_define, extract_variable_name_proc, extract_host_var_name, track_variable, track_host_var）
5. TsvWriter（write_tsv）
6. Reporter（print_report）
7. CLI（build_parser, main）
8. 実行スクリプト（run_proc.sh, run_proc.bat）
9. ユニットテスト（test_analyze_proc.py）
10. 統合テスト用フィクスチャ作成

## セキュリティ考慮事項

- Javaツールと同一方針（`--source-dir` の存在確認、`errors='replace'` でのエンコーディング無害化）

## パフォーマンス考慮事項

- ファイルキャッシュ: `_file_cache: dict[str, list[str]]` で同一ファイルの再読み込みを省略
- キャッシュ上限: `_MAX_FILE_CACHE_SIZE = 800`
- ASTキャッシュは不要（正規表現ベースのため）

## 将来の拡張性

- 3言語（Java / Pro*C / Shell）が揃った後にプラグイン型（案A）へリファクタリング
- アクセサ関数追跡（Pro*Cの第3段階相当）の追加
