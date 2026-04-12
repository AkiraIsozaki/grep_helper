# Java開発者のためのPython文法ガイド
## `analyze.py` を読むための最速入門

> **対象読者**: Javaの経験があるが、Pythonをほぼ知らない人  
> **目的**: `analyze.py` を読み解くために必要なPython文法を、Javaとの比較で習得する

---

## 目次

1. [ファイル構造と実行エントリーポイント](#1-ファイル構造と実行エントリーポイント)
2. [インポート](#2-インポート)
3. [型ヒント](#3-型ヒント)
4. [定数とモジュールレベル変数](#4-定数とモジュールレベル変数)
5. [Enum](#5-enum)
6. [データクラス（NamedTuple・@dataclass）](#6-データクラスnamedtupledataclass)
7. [関数定義](#7-関数定義)
8. [f-string（文字列補間）](#8-f-string文字列補間)
9. [コレクション操作（list・dict・set）](#9-コレクション操作listdictset)
10. [ファイル入出力（`with` 文）](#10-ファイル入出力with-文)
11. [正規表現](#11-正規表現)
12. [for ループとイテレーション](#12-for-ループとイテレーション)
13. [None の扱い](#13-none-の扱い)
14. [例外処理](#14-例外処理)
15. [関数内関数（ネスト関数）](#15-関数内関数ネスト関数)
16. [慣例・命名規則](#16-慣例命名規則)

---

## 1. ファイル構造と実行エントリーポイント

### Javaとの比較

Javaはクラスが必須だが、Pythonはクラスなしで関数を直接書ける。`main()` の呼び出しはファイル末尾に書く。

```python
# analyze.py 末尾 (1186行目付近)
def main() -> None:
    """エントリーポイント。"""
    parser = build_parser()
    args = parser.parse_args()
    ...
```

ただし `analyze.py` では末尾に `if __name__ == "__main__":` ガードがない。これは**ライブラリとして import されても main() が自動実行されない**という意図ではなく、このファイルが直接 `python analyze.py` で呼び出されることを前提にしているため。

| Java | Python |
|------|--------|
| `public static void main(String[] args)` | `def main() -> None:` |
| クラス必須 | クラス不要、トップレベルに関数を書ける |
| `System.out.println()` | `print()` |
| `System.err.println()` | `print(..., file=sys.stderr)` |

```python
# analyze.py 1199行目
print(
    f"エラー: --source-dir で指定したディレクトリが存在しません: {source_dir}",
    file=sys.stderr,   # ← キーワード引数でstderrに出力
)
sys.exit(1)            # ← Javaの System.exit(1) と同じ
```

---

## 2. インポート

### 基本構文

```python
# analyze.py 8〜17行目
import argparse       # ← import モジュール名（Java の import パッケージ に相当）
import csv
import re
import sys
from pathlib import Path          # ← from モジュール import クラス名
from typing import NamedTuple     # ← 複数importは from X import A, B でも可
from dataclasses import dataclass, field
from enum import Enum
```

| Java | Python |
|------|--------|
| `import java.util.List;` | `from typing import List` (古い) / 直接 `list` (3.9以降) |
| `import java.nio.file.Path;` | `from pathlib import Path` |
| `import java.util.regex.Pattern;` | `import re`（モジュールとして使う） |

### オプショナルな import（try/except による存在確認）

Javaに相当する構文はない。Pythonでは依存ライブラリが入っていない場合でも動作させたいとき、このイディオムを使う。

```python
# analyze.py 19〜23行目
try:
    import javalang
    _JAVALANG_AVAILABLE = True
except ImportError:
    _JAVALANG_AVAILABLE = False
```

その後、コード内で `if _JAVALANG_AVAILABLE:` と確認してからjavalangを使う。

```python
# analyze.py 241〜242行目
def get_ast(filepath: str, source_dir: Path) -> object | None:
    if not _JAVALANG_AVAILABLE:
        return None
```

### `from __future__ import annotations`

```python
# analyze.py 6行目
from __future__ import annotations
```

Python 3.10未満で `str | None` のような型ヒントを書くための互換宣言。これがあるとファイル全体の型ヒントが文字列として扱われ、前方参照や `|` 記法が3.12でなくても使えるようになる。**コードの動作自体には影響しない。**

---

## 3. 型ヒント

Pythonは動的型付け言語だが、**型ヒント（Type Hints）** でJavaのような型情報を付与できる。コンパイル時チェックはなく、IDEや静的解析ツール（mypy）が利用する。

### 変数の型ヒント

```python
# analyze.py 101〜115行目
_ast_cache: dict[str, object | None] = {}
_ast_line_index: dict[str, dict[int, tuple[str | None, str | None]]] = {}
_file_lines_cache: dict[str, list[str]] = {}
_java_files_cache: dict[str, list[Path]] = {}
_method_starts_cache: dict[str, list[int]] = {}
```

| Java | Python |
|------|--------|
| `Map<String, Object>` | `dict[str, object]` |
| `Map<String, List<String>>` | `dict[str, list[str]]` |
| `List<String>` | `list[str]` |
| `String` または `null` | `str \| None` |
| `Tuple<String, String>` (Javaにはないが) | `tuple[str, str]` |
| `Object` | `object` |

### 関数の型ヒント

```python
# analyze.py 121〜122行目
def parse_grep_line(line: str) -> dict | None:
    #                ^^^^^^^^     ^^^^^^^^^^^
    #                引数の型      戻り値の型
```

```python
# analyze.py 293〜295行目
def _get_or_build_ast_index(
    filepath: str, tree: object
) -> dict[int, tuple[str | None, str | None]]:
```

Javaと比べると：

```java
// Java
private Map<Integer, Tuple<String, String>> getOrBuildAstIndex(String filepath, Object tree)
```

### `|` によるユニオン型（Java にはない概念）

```python
str | None    # str か None のどちらか（Java の Optional<String> に近い）
str | Path    # str か Path のどちらか
```

---

## 4. 定数とモジュールレベル変数

Pythonはクラスの外にも変数を定義できる（モジュールレベル変数）。

### 定数

```python
# analyze.py 97〜98行目
_MAX_AST_CACHE_SIZE = 300    # Python に const キーワードはない
_MAX_FILE_CACHE_SIZE = 800   # 慣例として大文字スネークケースで定数を表す
```

> Javaの `static final int MAX_AST_CACHE_SIZE = 300;` に相当。ただしPythonは言語レベルで不変を保証しない。

### リストとタプルによる定数テーブル

```python
# analyze.py 30〜37行目
USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'@\w+\s*\('),                                  "アノテーション"),
    (re.compile(r'\bstatic\s+final\b'),                         "定数定義"),
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\.equals\s*\(|[!=]='), "条件判定"),
    (re.compile(r'\breturn\b'),                                  "return文"),
    (re.compile(r'\b\w[\w<>\[\]]*\s+\w+\s*='),                 "変数代入"),
    (re.compile(r'\w+\s*\('),                                    "メソッド引数"),
]
```

**タプル** `(a, b)` はJavaには対応物がない。「複数の値をひとまとめにした、変更不可能な配列」。  
この例では「正規表現パターンと分類名の組」を1エントリとしてリストに並べている。

---

## 5. Enum

```python
# analyze.py 51〜66行目
class RefType(Enum):
    """参照種別。"""
    DIRECT   = "直接"
    INDIRECT = "間接"
    GETTER   = "間接（getter経由）"


class UsageType(Enum):
    """使用タイプ（7種）。"""
    ANNOTATION = "アノテーション"
    CONSTANT   = "定数定義"
    VARIABLE   = "変数代入"
    CONDITION  = "条件判定"
    RETURN     = "return文"
    ARGUMENT   = "メソッド引数"
    OTHER      = "その他"
```

| Java | Python |
|------|--------|
| `enum RefType { DIRECT("直接"), ... }` | `class RefType(Enum): DIRECT = "直接"` |
| `RefType.DIRECT.getValue()` | `RefType.DIRECT.value` |
| `RefType.DIRECT.name()` | `RefType.DIRECT.name` |

Javaとの大きな違い：Pythonの `Enum` は `(Enum)` を継承して **クラスとして定義する**。

```python
# 使用例 (analyze.py 1055行目)
ref_order = 0 if r.ref_type == RefType.DIRECT.value else 1
#                               ^^^^^^^^^^^^^^^^^^
#                               .value で文字列 "直接" を取得
```

---

## 6. データクラス（NamedTuple・@dataclass）

### NamedTuple — イミュータブルなレコード型

```python
# analyze.py 69〜79行目
class GrepRecord(NamedTuple):
    """分析結果の1件を表すイミュータブルなデータモデル。"""
    keyword:    str         # 検索した文言
    ref_type:   str         # 参照種別
    usage_type: str         # 使用タイプ
    filepath:   str         # ファイルパス
    lineno:     str         # 行番号
    code:       str         # コード行
    src_var:    str = ""    # デフォルト値付きフィールド
    src_file:   str = ""
    src_lineno: str = ""
```

Javaのレコードクラスに近い：

```java
// Java 16以降のrecord（参考）
record GrepRecord(String keyword, String refType, ...) {}
```

**NamedTupleの特徴：**
- フィールドへのアクセスは `record.keyword` のようにドットアクセス（インデックスでもアクセス可）
- イミュータブル（変更不可）
- `tuple` のサブクラスなので軽量

```python
# 生成方法 (analyze.py 214〜221行目)
records.append(GrepRecord(
    keyword=keyword,
    ref_type=RefType.DIRECT.value,
    usage_type=usage_type,
    filepath=parsed["filepath"],
    lineno=parsed["lineno"],
    code=parsed["code"],
))
```

### @dataclass — ミュータブルなデータ保持クラス

```python
# analyze.py 82〜89行目
@dataclass
class ProcessStats:
    """処理統計。"""
    total_lines:     int = 0
    valid_lines:     int = 0
    skipped_lines:   int = 0
    fallback_files:  set[str] = field(default_factory=set)
    encoding_errors: set[str] = field(default_factory=set)
```

`@dataclass` は **デコレータ**（後述）で、`__init__` や `__repr__` を自動生成する。JavaのLombokの `@Data` に似た概念。

**`field(default_factory=set)` の注意点：**  
`set[str] = set()` と書けない。Pythonではデフォルト値にミュータブルなオブジェクトを直接書くと、すべてのインスタンスでそのオブジェクトが共有されてしまうバグが発生する。`default_factory` に生成関数を渡すことで、インスタンスごとに新しい `set` が作られる。

```python
# 使用例 (analyze.py 191, 222行目)
stats.total_lines += 1
stats.valid_lines += 1
stats.fallback_files.add(filepath)  # set への追加
```

---

## 7. 関数定義

### 基本構文

```python
# analyze.py 121〜157行目
def parse_grep_line(line: str) -> dict | None:
    """grep結果の1行をパースする。不正行はNoneを返す。

    Args:
        line: grep結果の1行

    Returns:
        {'filepath': str, 'lineno': str, 'code': str} または None
    """
    stripped = line.rstrip('\n\r')

    if not stripped.strip():    # 空行スキップ
        return None

    ...
    return {
        "filepath": filepath,
        "lineno":   lineno,
        "code":     code.strip(),
    }
```

- `def` キーワードで関数を定義（`public/private/static` は不要）
- ブロックは **インデント** で表す（`{}` は不要）
- 三重引用符 `"""..."""` が **ドキュメントコメント（docstring）**
- `return` は Javaと同じ

### デフォルト引数

```python
# analyze.py 435〜441行目
def determine_scope(
    usage_type: str,
    code: str,
    filepath: str = "",          # ← デフォルト値あり
    source_dir: Path | None = None,
    lineno: int = 0,
) -> str:
```

Javaにはないが、デフォルト引数を持つパラメータは末尾に置く必要がある。

### キーワード引数による呼び出し

```python
# analyze.py 206〜212行目
usage_type = classify_usage(
    code=parsed["code"],         # ← 引数名を明示して渡す
    filepath=parsed["filepath"],
    lineno=int(parsed["lineno"]),
    source_dir=source_dir,
    stats=stats,
)
```

Javaはメソッド呼び出しで引数名を書けないが、Pythonでは `引数名=値` で明示できる。順番を問わずに渡せるため、引数が多い関数で可読性が上がる。

### `*` アンパック（spread）

```python
# analyze.py 1120行目
for row in heapq.merge(*readers, key=_row_sort_key):
#                      ^^^^^^^^
#                      list を展開して可変長引数として渡す
```

JavaのStreamにある `flatMap` 的な概念ではなく、`heapq.merge(readers[0], readers[1], ...)` と書くのと同等。JavaにはSpread演算子はない。

---

## 8. f-string（文字列補間）

```python
# analyze.py 194〜198行目
print(
    f"  進捗: {path.name} {stats.total_lines:,} 行処理済み"
    f" (有効: {stats.valid_lines:,})",
    file=sys.stderr,
    flush=True,
)
```

`f"..."` は **f-string**（フォーマット文字列）。Javaの `String.format()` や `%s` の代わり。

| Java | Python |
|------|--------|
| `String.format("値: %d", n)` | `f"値: {n}"` |
| `String.format("%,d", n)` | `f"{n:,}"` （カンマ区切り） |
| `String.format("%.1f", n)` | `f"{n:.1f}"` |

```python
# analyze.py 1292行目
print(f"  {grep_path.name} → {output_path} (直接: {direct_count} 件, 間接: {indirect_count} 件)")
```

---

## 9. コレクション操作（list・dict・set）

### list（可変長配列）

```python
records: list[GrepRecord] = []    # 空リスト初期化

records.append(GrepRecord(...))   # 末尾追加 (Java の add())
records.extend(indirect)          # 別リストをすべて追加 (Java の addAll())
records.sort(key=_sort_key)       # ソート（破壊的）
sorted(some_list)                 # ソート（非破壊的、新リストを返す）

len(records)                      # 要素数 (Java の size())
```

```python
# analyze.py 1232行目
all_records: list[GrepRecord] = list(direct_records)
#                                ^^^^^^^^^^^^^^^^^
#                                list() でコピーを生成
```

### dict（マップ）

```python
# analyze.py 305〜306行目
usage_by_line: dict[int, str] = {}
scope_by_line: dict[int, str] = {}

# キーで取得。なければ None
entry = index.get(lineno)         # Java の map.getOrDefault(lineno, null) に相当

# キーが存在しなければデフォルト値をセットして返す
# analyze.py 1252行目
project_scope_tasks.setdefault(var_name, []).append(record)
# ↑ Java の computeIfAbsent(key, k -> new ArrayList<>()).add(record) に相当

# キーの存在確認
if cache_key in _ast_cache:       # Java の map.containsKey()
if key not in _file_lines_cache:  # Java の !map.containsKey()

# 最初のキーを取得して削除（analyze.py 281行目）
_file_lines_cache.pop(next(iter(_file_lines_cache)))
```

**`dict` アクセスイディオム比較：**

| Java | Python |
|------|--------|
| `map.get(key)` | `d.get(key)` → `None` if absent |
| `map.getOrDefault(k, v)` | `d.get(k, v)` |
| `map.containsKey(k)` | `k in d` |
| `map.computeIfAbsent(k, f)` | `d.setdefault(k, default_value)` |
| `map.remove(key)` | `del d[key]` または `d.pop(key)` |
| `map.entrySet()` で反復 | `for k, v in d.items():` |

### set（重複なし集合）

```python
# analyze.py 88〜89行目（dataclassのフィールドとして定義）
fallback_files:  set[str] = field(default_factory=set)
encoding_errors: set[str] = field(default_factory=set)

# 追加
stats.fallback_files.add(filepath)    # Java の set.add()

# 要素数
len(stats.fallback_files)             # Java の set.size()
```

### リスト内包表記（List Comprehension）

Javaにはない強力な構文。ループ＋条件でリストを生成できる。

```python
# analyze.py 927行目（簡略版の概念説明）
# 「|(パイプ)」で2つのsetをマージして全行番号のsetを作る
all_lines = set(usage_by_line) | set(scope_by_line)

# dict内包表記 (analyze.py 340行目)
index = {ln: (usage_by_line.get(ln), scope_by_line.get(ln)) for ln in all_lines}
#        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^
#        {キー: 値}                                           forループ

# Javaで書くと：
# Map<Integer, Tuple<...>> index = new HashMap<>();
# for (int ln : allLines) {
#     index.put(ln, new Tuple<>(usageByLine.get(ln), scopeByLine.get(ln)));
# }
```

---

## 10. ファイル入出力（`with` 文）

### `with` 文（コンテキストマネージャ）

Javaの `try-with-resources` に相当する。ブロックを抜けると自動でファイルが閉じられる。

```python
# analyze.py 189〜190行目
with open(path, encoding="cp932", errors="replace") as f:
    for line in f:        # ← 1行ずつイテレート（Java の BufferedReader.readLine() のループ相当）
        stats.total_lines += 1
        ...
```

```python
# analyze.py 1074〜1081行目（CSV書き込み）
with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(_TSV_HEADERS)         # ヘッダー行
    for r in records:
        writer.writerow([r.keyword, r.ref_type, ...])
```

| Java | Python |
|------|--------|
| `new FileReader(path)` + `try-with-resources` | `with open(path) as f:` |
| `reader.readLine()` ループ | `for line in f:` |
| `"UTF-8"` エンコーディング | `encoding="utf-8"` |
| BOM付きUTF-8 | `encoding="utf-8-sig"` |

### `pathlib.Path`

Javaの `java.nio.file.Path` に相当するが、よりシンプル。

```python
# analyze.py 256〜261行目
candidate = Path(filepath)
if not candidate.is_absolute():
    candidate = source_dir / filepath    # ← / 演算子でパス結合（Java の resolve()）

if not candidate.exists():
    return None

source = candidate.read_text(encoding="shift_jis", errors="replace")
#                 ^^^^^^^^^^
#                 ファイル全体を文字列として読む
```

| Java (`Path`) | Python (`pathlib.Path`) |
|---------------|------------------------|
| `path.isAbsolute()` | `path.is_absolute()` |
| `path.resolve(other)` | `path / other` |
| `Files.exists(path)` | `path.exists()` |
| `Files.readString(path)` | `path.read_text(encoding=...)` |
| `path.getFileName().toString()` | `path.name` |
| `path.getParent()` | `path.parent` |
| `path.toFile().mkdir()` | `path.mkdir(parents=True, exist_ok=True)` |
| `Files.walk(path)` で `.java` フィルタ | `path.rglob("*.java")` |

---

## 11. 正規表現

Javaの `java.util.regex.Pattern` に相当する `re` モジュールを使う。

```python
# analyze.py 40〜44行目（プリコンパイル）
_BINARY_PATTERN = re.compile(r'^Binary file .+ matches$')
_GREP_LINE_PATTERN = re.compile(r':(\d+):')
```

`r'...'` は **raw文字列**。バックスラッシュをエスケープせずに書ける。Javaで `\\d` と書くところを `\d` と書ける。

```python
# 使用方法
if _BINARY_PATTERN.match(stripped):     # 行頭からマッチ (Java の matcher.matches() に近い)
    return None

parts = _GREP_LINE_PATTERN.split(stripped, maxsplit=1)  # 分割

if pattern.search(line):               # 文字列内の任意位置にマッチ (Java の matcher.find())
    ...

for m in combined.finditer(line):      # 全マッチをイテレート
    matched_name = m.group(1)          # キャプチャグループ1番 (Java の group(1))
```

| Java | Python |
|------|--------|
| `Pattern.compile("...")` | `re.compile(r'...')` |
| `pattern.matcher(s).matches()` | `pattern.match(s)` （行頭のみ） |
| `pattern.matcher(s).find()` | `pattern.search(s)` （任意位置） |
| `matcher.group(1)` | `m.group(1)` |
| `string.split(pattern)` | `pattern.split(string)` |
| `"\\d"` | `r'\d'` または `"\\d"` |

---

## 12. for ループとイテレーション

### 基本 for-each

```python
# analyze.py 699〜714行目
for java_file in _get_java_files(source_dir):    # Javaのfor-eachと同じ発想
    filepath_str = str(java_file)
    lines = _cached_read_lines(filepath_str, stats)
    if not lines:
        continue                                   # Javaの continue と同じ
    records.extend(...)
```

### `enumerate` — インデックス付き反復

```python
# analyze.py 597〜602行目
for i, line in enumerate(lines[method_start - 1:], start=method_start):
#   ^  ^^^^                                          ^^^^^^^^^^^^^^^^
#   i=行番号   line=行内容                            開始番号を指定
    brace_count += line.count('{') - line.count('}')
    if found_open and brace_count <= 0:
        return (method_start, i)
```

Javaで書くと：
```java
for (int i = methodStart; i < lines.length; i++) {
    String line = lines[i - 1];
    ...
}
```

### `enumerate(lines, start=1)` パターン

```python
# analyze.py 882〜884行目
for i, line in enumerate(lines, start=1):    # 1始まりのインデックス
    if not pattern.search(line):
        continue
```

### タプルのアンパック（複数変数への代入）

```python
# analyze.py 149行目
filepath, lineno, code = parts
#^^^^^^^^  ^^^^^^  ^^^^
# 3要素のlistやtupleを一度に3変数に展開

# analyze.py 781行目
start_line, end_line = method_scope    # tuple(int, int) を2変数に展開
```

Javaには対応構文がない（Scalaなどにはある）。

### `for _, node in tree:` の `_`

```python
# analyze.py 308行目
for _, node in tree:
#   ^
#   使わない値は _ という名前にする慣例
```

Javaでは使わない変数でも名前をつけるが、Pythonでは `_` を使うことで「意図的に捨てている」ことを示す。

---

## 13. None の扱い

Pythonの `None` はJavaの `null` に相当する。

```python
# analyze.py 388〜392行目
tree = get_ast(filepath, source_dir)

if tree is None:                          # Javaの tree == null に相当
    if _JAVALANG_AVAILABLE:
        stats.fallback_files.add(filepath)
    return classify_usage_regex(code)
```

**`is None` vs `== None`：**  
`None` の比較は `==` ではなく `is` を使う慣例（PEP8）。`is` は同一オブジェクトかどうかを確認する（Javaの `==` に相当）、`==` は等値比較（Javaの `.equals()` に相当）。

### 真偽値として評価される `None`・空コレクション

```python
# analyze.py 278行目
if key not in _file_lines_cache:

# analyze.py 703〜704行目
lines = _cached_read_lines(filepath_str, stats)
if not lines:    # ← lines が空リスト [] か None のとき True
    continue
```

Pythonでは `None`・`0`・空リスト `[]`・空文字列 `""` はすべて `False` として評価される（Falsy値）。

| Java | Python |
|------|--------|
| `obj == null` | `obj is None` |
| `obj != null` | `obj is not None` |
| `list.isEmpty()` | `not list` または `len(list) == 0` |
| `str == null \|\| str.isEmpty()` | `not str` |

---

## 14. 例外処理

```python
# analyze.py 264〜271行目
try:
    source = candidate.read_text(encoding="shift_jis", errors="replace")
    tree = javalang.parse.parse(source)
    _ast_cache[cache_key] = tree
except Exception:
    # javalang.parser.JavaSyntaxError を含む全例外をフォールバック扱い
    _ast_cache[cache_key] = None
```

| Java | Python |
|------|--------|
| `try { ... }` | `try:` |
| `catch (Exception e) { ... }` | `except Exception:` または `except Exception as e:` |
| `catch (IOException \| ParseException e)` | `except (IOException, ParseException):` |
| `finally { ... }` | `finally:` |
| `throw new RuntimeException(msg)` | `raise RuntimeError(msg)` |

```python
# analyze.py 1116〜1128行目
try:
    with open(output_path, ...) as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(_TSV_HEADERS)
        for row in heapq.merge(*readers, key=_row_sort_key):
            writer.writerow(row)
finally:
    for h in handles:
        h.close()
```

---

## 15. 関数内関数（ネスト関数）

Pythonでは関数の中に関数を定義できる。Javaのラムダや匿名クラスに似た用途で使われる。

```python
# analyze.py 1051〜1057行目
def write_tsv(records: list[GrepRecord], output_path: Path) -> None:
    """..."""

    def _sort_key(r: GrepRecord) -> tuple:    # ← write_tsv の中にだけ存在する関数
        def_file   = r.src_file   if r.src_file   else r.filepath
        def_lineno = int(r.src_lineno) if r.src_lineno.isdigit() else (
                     int(r.lineno)    if r.lineno.isdigit()     else 0)
        ref_order  = 0 if r.ref_type == RefType.DIRECT.value else 1
        lineno_int = int(r.lineno) if r.lineno.isdigit() else 0
        return (r.keyword, def_file, def_lineno, ref_order, r.filepath, lineno_int)

    records.sort(key=_sort_key)   # ← sort の比較関数として渡す
```

**三項演算子（条件式）：**

```python
# Pythonの条件式
def_file = r.src_file if r.src_file else r.filepath
#          ^^^^^^^^^^ if 条件      else 偽の場合
```

Javaの三項演算子 `r.srcFile != null ? r.srcFile : r.filepath` に相当。

**関数を引数として渡す：**

```python
records.sort(key=_sort_key)
#                ^^^^^^^^^
#                関数を値として渡す（Java の Comparator.comparing() に相当）
```

---

## 16. 慣例・命名規則

### アンダースコアプレフィックス

```python
_BINARY_PATTERN = ...        # モジュールレベルの「非公開」定数/変数
_ast_cache: dict = {}        # モジュールレベルの「非公開」変数

def _classify_by_ast(...):   # 「非公開」関数（Javaの private メソッドに相当）
def _sort_key(r):            # 同上（特に関数内関数でよく使う）
```

Pythonに `private` キーワードはない。`_` で始まる名前は **「このモジュール外から使わないでください」** という慣例。

### `__` ダブルアンダースコア（dunder）

```python
if __name__ == "__main__":    # スクリプトとして直接実行された場合のみ true
    main()
```

`__name__` のような `__X__` 形式はPythonの特殊属性・メソッド。`__init__` はコンストラクタに相当する。

### セミコロン不要

Javaと違い、文末にセミコロン `;` は不要（あっても動くが書かない）。

### ブロックはインデント

```python
def foo():
    if condition:
        do_something()    # 4スペースのインデントが標準
    else:
        do_other()
```

`{}` は存在しない。インデントがブロックを定義する。インデントがずれるとエラーになる。

---

## 付録：`analyze.py` で使われている主要Pythonイディオム早見表

| コード例 (analyze.py) | 意味 |
|----------------------|------|
| `path.stem` | ファイル名から拡張子を除いた部分 (例: `"foo.grep"` → `"foo"`) |
| `int(parsed["lineno"])` | 文字列を整数に変換 (Java の `Integer.parseInt()`) |
| `str(java_file)` | オブジェクトを文字列に変換 (Java の `.toString()`) |
| `sorted(...)` | 新しいソート済みリストを返す（非破壊） |
| `list.sort(key=f)` | リストをインプレースでソート（破壊的） |
| `"foo".isdigit()` | 数字文字列かどうか確認 |
| `"foo".isidentifier()` | 識別子として有効かどうか確認 |
| `"FOO".upper()` / `[0].upper()` | 大文字化 |
| `code.strip()` | 前後の空白除去 (Java の `trim()`) |
| `code.rstrip('\n\r')` | 末尾の特定文字除去 |
| `decl.split('=')[0]` | 最初の `=` で分割し最初の部分を取得 |
| `tokens[-1]` | リストの末尾要素（Javaにはない負インデックス） |
| `del _ast_cache[oldest]` | dict からキーを削除 |
| `list(set(candidates))` | set で重複除去してから list に戻す |
| `hasattr(node, "position")` | 属性の存在確認 (Java の `instanceof` + null チェックの組み合わせ) |
| `getattr(node, "modifiers", set())` | 属性取得（なければデフォルト値）|
| `isinstance(node, javalang.tree.Annotation)` | 型確認 (Java の `instanceof`) |
| `f"{n:,}"` | 数値をカンマ区切りでフォーマット |
| `f"{n:.1f}"` | 小数点以下1桁でフォーマット |
| `1_000_000` | 数値リテラルの桁区切り（可読性向上のためのシンタックスシュガー） |
