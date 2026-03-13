# プロジェクト用語集 (Glossary)

## 概要

このドキュメントは、grep_analyzer プロジェクトで使用される用語の定義を管理します。

**更新日**: 2026-03-13

---

## ドメイン用語

### 文言（もんごん）

**定義**: grepで検索する対象の文字列値（例: `"777"`, `"ERROR_CODE"`, `"STATUS_OK"`）

**説明**:
Javaプロジェクト内でビジネスコードやステータス値として使われる文字列リテラル。
本ツールでは「入力ファイル名（拡張子なし）」として扱われ、TSVの「文言」列の値となる。

**関連用語**: [grep結果ファイル](#grep結果ファイル), [直接参照](#直接参照)

**使用例**:
- `input/777.grep` → 文言 = `777`
- `input/ERROR_CODE.grep` → 文言 = `ERROR_CODE`

**英語表記**: keyword / search term

---

### grep結果ファイル

**定義**: ユーザーが手動実行した `grep -rn "文言" /path/to/java` の出力を保存したテキストファイル

**説明**:
`input/` ディレクトリに `[文言].grep` の形式で配置する。
フォーマット: `ファイルパス:行番号:コード行`

**関連用語**: [文言](#文言文もんごん), [input/ディレクトリ](#inputディレクトリ)

**使用例**:
```
src/main/java/Constants.java:10:    public static final String CODE = "777";
src/main/java/Service.java:30:    if (x.equals("777")) {
```

---

### 直接参照

**定義**: grepヒット行に文言リテラルが直接記述されている参照

**説明**:
第1段階で検出する。grep結果のファイルパス+行番号でソースを開き、AST解析で使用タイプを分類する。

**関連用語**: [間接参照](#間接参照), [参照種別](#参照種別)

**使用例**:
```java
// 直接参照の例（"777" がリテラルとして出現）
public static final String CODE = "777";
if (x.equals("777")) {
log.info("status: 777");
```

**TSVでの表示**: `参照種別` = `直接`

---

### 間接参照

**定義**: 文言リテラルを格納した変数/定数を介して、その値が使われている参照

**説明**:
第2段階で検出する。「定数定義」「変数代入」に分類された行から変数名を抽出し、
その変数が使われている箇所をスコープに応じて追跡する。

**関連用語**: [直接参照](#直接参照), [追跡スコープ](#追跡スコープ), [参照種別](#参照種別)

**使用例**:
```java
// 直接参照（第1段階で検出）
public static final String CODE = "777";   // ← Constants.java:10

// 間接参照（第2段階で検出）- grepでは出てこない
if (someVar.equals(CODE)) { ... }          // ← Service.java:110
someService.process(CODE);                 // ← Handler.java:55
```

**TSVでの表示**: `参照種別` = `間接`

---

### getter経由参照

**定義**: privateフィールドに代入された文言値が、getterメソッド経由で外部に渡される参照

**説明**:
第3段階で検出する。フィールドの同一クラス内からgetter候補を特定し、
プロジェクト全体でそのgetter呼び出し箇所を追跡する。
false positiveは許容（もれなく優先）。

**関連用語**: [間接参照](#間接参照), [getter候補](#getter候補)

**使用例**:
```java
// フィールドへの代入（直接参照、第1段階）
private String type = "777";               // ← Entity.java:8

// getter定義（同一クラス内、第3段階で検出）
public String getType() { return type; }   // ← Entity.java:20

// getter呼び出し（プロジェクト全体追跡）
someService.process(obj.getType());        // ← Handler.java:55
```

**TSVでの表示**: `参照種別` = `間接（getter経由）`

---

### 参照種別

**定義**: 文言の参照方法を示す分類値（TSVの「参照種別」列）

**取りうる値**:

| 値 | 意味 |
|---|------|
| `直接` | 文言リテラルが直接コードに出現している |
| `間接` | 変数/定数経由で値が使われている |
| `間接（getter経由）` | getterメソッド経由で値が外部に渡されている |

---

### 使用タイプ

**定義**: Javaコードにおける文言または変数/定数の使われ方を示す分類値（TSVの「使用タイプ」列）

**取りうる値（7種）**:

| 使用タイプ | 内容 | 例 |
|----------|------|----|
| アノテーション | `@Annotation("値")` または `@Annotation(変数)` | `@RequestMapping("777")` |
| 定数定義 | `static final TYPE NAME = "値"` | `public static final String CODE = "777"` |
| 変数代入 | ローカル変数・フィールドへの代入 | `String type = "777"` |
| 条件判定 | `if/else if/while` の条件、`.equals()`、`==`/`!=` 比較 | `if (x.equals("777"))` |
| return文 | `return "値"` または `return 変数` | `return CODE;` |
| メソッド引数 | メソッド呼び出しの引数として渡している | `process(CODE)` |
| その他 | 上記に当てはまらないもの（コメント行・文字列連結など） | `// 777 はここで使う` |

**注意**: コメント行もスキップせず「その他」として出力する（もれなく優先）

---

### 追跡スコープ

**定義**: 間接参照追跡時に検索する範囲

**説明**:
変数の種類によって誤ヒットリスクが異なるため、スコープを分けて追跡する。

**スコープ一覧**:

| 変数の種類 | 例 | 追跡スコープ | 理由 |
|-----------|-----|-------------|------|
| 定数（`static final`） | `public static final String CODE = "777"` | **プロジェクト全体** | 名前が意味を持ち誤ヒットが少ない |
| フィールド | `private String type = "777"` | **同一クラス内** + **getter経由でプロジェクト全体** | クラス外からはgetterで参照される |
| ローカル変数 | `String s = "777"` | **同一メソッド内** | 汎用名が多く全体検索は誤ヒットが大量発生 |

---

### getter候補

**定義**: フィールドの値を外部に返す可能性があるメソッド

**説明**:
以下の2方法で特定する:
1. **命名規則**: フィールド名 `type` → `getType()` のメソッドを探す
2. **return文解析**: `return フィールド名;` しているメソッドを全て拾う（非標準命名も対象）

**使用例**:
```java
private String type = "777";

// 命名規則で検出
public String getType() { return type; }

// return文解析で検出（非標準命名）
public String fetchOrderType() { return type; }
```

---

## 技術用語

### javalang

**定義**: PythonからJava 7以上のソースコードをAST（抽象構文木）解析するライブラリ

**本プロジェクトでの用途**:
Javaコード行の使用タイプ分類（アノテーション/定数定義/変数代入/条件判定/return文/メソッド引数）にAST解析を使用。
パースエラー時は正規表現フォールバックで処理を継続する。

**バージョン**: `>=0.13.0,<1.0.0`

**関連ドキュメント**: [アーキテクチャ設計書](./architecture.md)

---

### ASTキャッシュ

**定義**: 同一Javaファイルの繰り返しAST解析を防ぐオンメモリのキャッシュ

**説明**:
`_ast_cache: dict[str, object | None]` としてモジュールレベルで定義。
- `object`: パース成功時のjavalang ASTオブジェクト
- `None`: パースエラーが発生したファイル（正規表現フォールバックを使用）

**使用例**:
```python
_ast_cache: dict[str, object | None] = {}

if filepath not in _ast_cache:
    source = read_java_file(filepath)
    try:
        _ast_cache[filepath] = javalang.parse.parse(source)
    except javalang.parser.JavaSyntaxError:
        _ast_cache[filepath] = None  # フォールバック対象としてマーク
```

---

### 正規表現フォールバック

**定義**: javalangのAST解析が失敗した場合に使用する代替の使用タイプ分類方式

**説明**:
`USAGE_PATTERNS` リストに定義された優先度順の正規表現パターンで分類する。
AST解析より精度は低いが、処理を中断せずに継続できる。
フォールバックが発生したファイルは `ProcessStats.fallback_files` に記録する。

**関連用語**: [使用タイプ](#使用タイプ), [ASTキャッシュ](#astキャッシュ)

---

### venv

**定義**: Pythonの標準仮想環境機能

**本プロジェクトでの用途**:
外部依存（javalang）をシステムのPython環境に影響なくインストールするために使用。
`setup.sh` / `setup.bat` で自動作成される。`run.sh` / `run.bat` 実行時に自動有効化。

**バージョン**: Python 3.8+ 同梱

---

### TSV（Tab-Separated Values）

**定義**: タブ文字で列を区切ったテキスト形式のファイル

**本プロジェクトでの用途**:
分析結果の出力形式。UTF-8 BOM付きで出力することでWindowsのExcelで文字化けなく開ける。

**エンコード**: `utf-8-sig`（UTF-8 BOM付き）

**ソート順**: 文言 → ファイルパス → 行番号（昇順）

---

## 略語・頭字語

### AST

**正式名称**: Abstract Syntax Tree（抽象構文木）

**意味**: プログラムのソースコードを構文的に解析し、木構造で表現したもの

**本プロジェクトでの使用**:
javalangを使ってJavaソースコードをAST解析し、各コード行の使用タイプ（定数定義・条件判定等）を判定する

---

### BOM

**正式名称**: Byte Order Mark

**意味**: テキストファイルの先頭に付加されるバイト列。文字コードを識別するために使用

**本プロジェクトでの使用**:
TSV出力をExcelで文字化けなく開けるよう、UTF-8 BOM付き（`utf-8-sig`）で出力する

---

### PRD

**正式名称**: Product Requirements Document（プロダクト要求定義書）

**意味**: プロダクトの要件・機能・非機能要件を定義したドキュメント

**本プロジェクトでの使用**: `docs/product-requirements.md`

---

## アーキテクチャ用語

### パイプラインアーキテクチャ

**定義**: データが段階的に変換される処理フロー

**本プロジェクトでの適用**:
`入力レイヤー（GrepParser）→ 分析レイヤー（Classifier + Tracker）→ 出力レイヤー（TsvWriter）` の3段階パイプライン

**関連コンポーネント**: `GrepParser`, `UsageClassifier`, `IndirectTracker`, `GetterTracker`, `TsvWriter`

**図解**:
```
grep結果ファイル
    ↓ (GrepParser)
直接参照レコード（未分類）
    ↓ (UsageClassifier)
直接参照レコード（分類済み）
    ↓ (IndirectTracker + GetterTracker)
間接参照レコード（分類済み）
    ↓ (TsvWriter)
output/[文言].tsv
```

---

## ステータス・状態

### 処理ステータス（ProcessStats）

| フィールド | 意味 |
|-----------|------|
| `total_lines` | 入力したgrep行の総数 |
| `valid_lines` | 正常にパースできた行数 |
| `skipped_lines` | スキップした行数（バイナリ通知・空行・不正形式） |
| `fallback_files` | ASTフォールバックが発生したファイルの一覧 |
| `encoding_errors` | エンコーディングエラーが発生したファイルの一覧 |

---

## エラー・例外

### 入力エラー（exit code 1）

**発生条件**:
- `--source-dir` が未指定
- `--source-dir` / `--input-dir` が存在しないまたはディレクトリでない
- `input/` にgrep結果ファイルが1件もない

**対処方法**: stderrに日本語でエラーメッセージを表示し終了

---

### 実行時エラー（exit code 2）

**発生条件**: 予期しない例外（メモリ不足・権限エラー等）

**対処方法**: stderrにエラー内容を表示し終了

---

### ASTパースエラー（継続）

**発生条件**: `javalang.parser.JavaSyntaxError` - Javaファイルの文法が解析不能

**対処方法**:
- 正規表現フォールバックで分類を継続
- `stats.fallback_files` に記録
- 処理完了後のサマリに件数を表示

---

### エンコーディングエラー（継続）

**発生条件**: Javaファイルの文字コード（Shift-JIS）読み込み時のデコードエラー

**対処方法**:
- `errors='replace'` で置換文字に変換して処理継続
- `stats.encoding_errors` に記録
- 処理完了後のサマリに件数を表示
