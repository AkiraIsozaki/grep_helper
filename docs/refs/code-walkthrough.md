# analyze.py コード解説（Java経験者向け）

Python に不慣れな方向けに、Java との対比を交えながら analyze.py の全処理ロジックを解説します。
単純な箇所は簡潔に、難しい箇所・設計上の判断が必要な箇所は「**なぜそうなっているか**」と
「**具体例**」を使って説明します。

---

## 目次

1. [このツールが何をするか（全体像）](#1-このツールが何をするか全体像)
2. [Python 基礎対照表（Java との違い）](#2-python-基礎対照表java-との違い)
3. [ファイル先頭：import と定数定義](#3-ファイル先頭import-と定数定義)
4. [データモデル：Enum / dataclass](#4-データモデルenum--dataclass)
5. [処理フロー全体図](#5-処理フロー全体図)
6. [段階①：CLI 起動（build_parser / main）](#6-段階cli-起動build_parser--main)
7. [段階②：grep ファイルの読み込み（process_grep_file / parse_grep_line）](#7-段階grep-ファイルの読み込みprocess_grep_file--parse_grep_line)
8. [段階③：使用タイプ分類（classify_usage / get_ast / _classify_by_ast）](#8-段階使用タイプ分類classify_usage--get_ast--_classify_by_ast)
9. [段階④：間接参照の追跡（IndirectTracker 群）](#9-段階間接参照の追跡indirecttracker-群)
10. [段階⑤：getter 経由参照の追跡（GetterTracker 群）](#10-段階getter-経由参照の追跡gettertracker-群)
11. [段階⑥：TSV 出力（write_tsv）](#11-段階tsv-出力write_tsv)
12. [段階⑦：処理サマリ表示（print_report）](#12-段階処理サマリ表示print_report)
13. [AST キャッシュのしくみ](#13-ast-キャッシュのしくみ)

---

## 1. このツールが何をするか（全体像）

Java プロジェクトを対象に、特定の文言（定数値など）を grep した結果ファイルを受け取り、
**その文言がどのような文脈で使われているか**を自動分類して TSV に出力するツールです。

```
[入力] input/SAMPLE.grep

tests/fixtures/java/Constants.java:9:    public static final String SAMPLE_CODE = "SAMPLE";
tests/fixtures/java/Constants.java:13:       if (value.equals(SAMPLE_CODE)) {
tests/fixtures/java/Entity.java:8:    private String type = "SAMPLE";
```

```
[出力] output/SAMPLE.tsv

文言    参照種別          使用タイプ  ファイル          行  コード行
SAMPLE  直接              定数定義    Constants.java    9   public static final ...
SAMPLE  直接              条件判定    Constants.java    13  if (value.equals ...
SAMPLE  直接              変数代入    Entity.java       8   private String type = ...
SAMPLE  間接              条件判定    Constants.java    13  if (value.equals ...   ← SAMPLE_CODE 経由を追跡
SAMPLE  間接（getter経由）条件判定    Service.java      10  if (entity.getType()... ← getter 経由を追跡
```

処理は 3 段階：
1. **直接参照**：grep 結果の各行を分類（定数定義 / 条件判定 / return文 など7種）
2. **間接参照**：変数・定数・フィールドに代入された場合、その変数の使用箇所を追跡
3. **getter 経由**：フィールドに getter があれば、getter 呼び出し箇所も追跡

---

## 2. Python 基礎対照表（Java との違い）

コードを読む前に、Java と Python の構文対応を確認します。

| Java | Python | 補足 |
|---|---|---|
| `import java.util.List;` | `from pathlib import Path` | パッケージ構造がなくファイル単位 |
| `null` | `None` | 同じ意味 |
| `void method()` | `def method() -> None:` | 戻り値型はアノテーション（省略可） |
| `String s;` | 型宣言不要 | 型ヒント `s: str` は任意 |
| `"Hello " + name` | `f"Hello {name}"` | f-string（フォーマット文字列）|
| `List<String>` | `list[str]` | ジェネリクスに相当 |
| `Map<String, Object>` | `dict` | ディクショナリ |
| `"a b c".split(" ")` | `"a b c".split()` | 引数なしだと連続空白もまとめて分割 |
| `for (String s : list)` | `for s in list:` | コロンでブロック開始、インデントで範囲 |
| `instanceof` | `isinstance(obj, Type)` | 型チェック |
| `try { } catch(Exception e) { }` | `try: ... except Exception: ...` | |
| `public static final` | モジュールレベルの変数（大文字慣習）| クラス外に置く |
| `@Override` などのアノテーション | `@dataclass` などのデコレータ | `@` で始まる点は同じ |
| `Optional<T>` | `T \| None` または `Optional[T]` | Union 型 |
| `System.exit(1)` | `sys.exit(1)` | 同じ |
| `System.err.println(...)` | `print(..., file=sys.stderr)` | 標準エラー出力 |
| `Collections.sort(list, comparator)` | `sorted(list, key=func)` | 元のリストを変えず新しいリストを返す |
| `Map.containsKey(k)` | `k in dict` | キーの存在確認 |

---

## 3. ファイル先頭：import と定数定義

```python
import argparse   # CLI 引数パーサ（Java の Commons CLI に相当）
import csv        # CSV/TSV の読み書き
import re         # 正規表現（Java の Pattern / Matcher に相当）
import sys        # sys.exit() / sys.stderr
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path                   # ファイルパス操作（Java の Path と同じ）

try:
    import javalang        # Java AST パーサ（pip でインストール）
    _JAVALANG_AVAILABLE = True
except ImportError:
    _JAVALANG_AVAILABLE = False
```

> **なぜ `try/except ImportError` で囲むのか**
>
> `javalang` は必須ではなく、インストールされていなくても正規表現フォールバックで動作させたいからです。
> Java だと「クラスが存在しなければ実行時に `ClassNotFoundException`」ですが、Python では
> `import` 時に即座に `ImportError` が発生するため、それを捕捉してフラグを立てます。
> こうすることで、ライブラリが入っていない環境でも `if _JAVALANG_AVAILABLE:` の分岐で
> ツールを動作させ続けられます。

---

### 正規表現パターンの事前コンパイル

```python
USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'@\w+\s*\('),                                  "アノテーション"),
    (re.compile(r'\bstatic\s+final\b'),                         "定数定義"),
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\.equals\s*\(|[!=]='), "条件判定"),
    (re.compile(r'\breturn\b'),                                  "return文"),
    (re.compile(r'\b\w[\w<>\[\]]*\s+\w+\s*='),                 "変数代入"),
    (re.compile(r'\w+\s*\('),                                    "メソッド引数"),
]
```

`list[tuple[re.Pattern, str]]` は「(コンパイル済み正規表現, ラベル文字列) のペアのリスト」です。
Java の `List<Map.Entry<Pattern, String>>` に相当します。

> **なぜ関数内ではなくモジュールレベルで `re.compile()` するのか**
>
> `re.compile()` は正規表現の構文解析を行うためコストがかかります。
> 関数内に書くと、その関数が呼ばれるたびに毎回コンパイルが走ります。
> モジュールレベルに置くことで、プロセス起動時の1回だけで済みます。
> Java で `static final Pattern` にするのと同じ理由です。

> **優先度の仕組みと順序設計**
>
> リストの先頭から順番に評価し、最初にマッチしたラベルを返します。
> この順序が重要で、例えば `return a.equals(CODE);` は `\breturn\b` にも
> `.equals\s*\(` にもマッチします。`.equals` が先に並んでいるため「条件判定」になります。
> これは「`return` の中で比較しているならば、本質的な用途は条件判定」という
> 設計判断を優先度として表現したものです。

**【具体例】優先度による分類結果**

| コード行 | マッチするパターン（複数） | 結果 |
|---|---|---|
| `@RequestMapping("SAMPLE")` | アノテーション | **アノテーション** |
| `public static final String X = "SAMPLE"` | 定数定義、変数代入 | **定数定義**（先に来るため） |
| `return a.equals("SAMPLE");` | 条件判定（`.equals`）、return文 | **条件判定**（先に来るため） |
| `return "SAMPLE";` | return文 | **return文** |
| `String msg = "SAMPLE";` | 変数代入 | **変数代入** |
| `log.info("SAMPLE");` | メソッド引数 | **メソッド引数** |
| `// SAMPLE はここで使う` | どれにもマッチしない | **その他** |

---

## 4. データモデル：Enum / dataclass

### Enum

```python
class RefType(Enum):
    DIRECT   = "直接"
    INDIRECT = "間接"
    GETTER   = "間接（getter経由）"
```

Java の `enum RefType { DIRECT("直接"), ... }` と同じです。
値を取り出すには `.value` を使います：`RefType.DIRECT.value` → `"直接"`

### GrepRecord（イミュータブルな結果1件）

```python
@dataclass(frozen=True)
class GrepRecord:
    keyword:    str        # 検索した文言（入力ファイル名から取得）
    ref_type:   str        # 参照種別（RefType.value）
    usage_type: str        # 使用タイプ（UsageType.value）
    filepath:   str        # Javaファイルのパス
    lineno:     str        # 行番号（※文字列のまま保持）
    code:       str        # コード行
    src_var:    str = ""   # 間接参照の場合：経由した変数名
    src_file:   str = ""   # 間接参照の場合：変数が定義されたファイル
    src_lineno: str = ""   # 間接参照の場合：変数が定義された行番号
```

`@dataclass(frozen=True)` は Java の `record` クラスに相当します。
フィールドを宣言するだけでコンストラクタ・`__eq__`（equals）・`__hash__`（hashCode）が自動生成されます。

**【具体例】直接参照と間接参照で src_* の埋まり方が変わる**

```
直接参照レコード（src_var/src_file/src_lineno は空）：
  keyword="SAMPLE", ref_type="直接", usage_type="定数定義",
  filepath="Constants.java", lineno="9",
  code='public static final String SAMPLE_CODE = "SAMPLE";',
  src_var="", src_file="", src_lineno=""

間接参照レコード（SAMPLE_CODE 経由で見つかった使用箇所）：
  keyword="SAMPLE", ref_type="間接", usage_type="条件判定",
  filepath="Constants.java", lineno="13",
  code="if (value.equals(SAMPLE_CODE)) {",
  src_var="SAMPLE_CODE",              ← 経由した変数名
  src_file="Constants.java",          ← SAMPLE_CODE が定義されていたファイル
  src_lineno="9"                      ← SAMPLE_CODE が定義されていた行
```

> **なぜ `frozen=True`（イミュータブル）にするのか**
>
> 一度生成したレコードを後から変更する必要がないため、変更できないようにします。
> `frozen=True` にすると、生成後にフィールドを書き換えようとすると例外が発生するため、
> 「途中で内容が変わっていた」バグを防げます。
> また `frozen=True` があると `__hash__` も自動生成されるため、
> set や dict のキーとして使えるようになります。

> **なぜ `lineno` が `int` ではなく `str` なのか**
>
> grep ファイルから読んだ行番号は文字列です。TSV に書き出すときも文字列のまま使います。
> `int` に変換するのは「数値ソート」「メソッドスコープ検索」など整数が必要な局所的な場面だけなので、
> `int(record.lineno)` と必要な箇所だけキャストするほうがシンプルです。

### ProcessStats（処理統計）

```python
@dataclass
class ProcessStats:
    total_lines:     int = 0
    valid_lines:     int = 0
    skipped_lines:   int = 0
    fallback_files:  list[str] = field(default_factory=list)
    encoding_errors: list[str] = field(default_factory=list)
```

> **なぜリストのデフォルト値に `= []` と書けないのか**
>
> Python の関数・クラス定義におけるデフォルト引数／フィールドは「定義時に1回だけ評価」されます。
> `= []` と書いてしまうと、すべてのインスタンスが同一のリストオブジェクトを共有してしまいます。
>
> ```python
> # BAD: stats1 と stats2 が同じリストを指す
> stats1 = ProcessStats()
> stats2 = ProcessStats()
> stats1.fallback_files.append("Foo.java")
> print(stats2.fallback_files)  # → ["Foo.java"] ← 混入！意図していない動作
> ```
>
> `field(default_factory=list)` を使うと、インスタンス生成のたびに `list()` が呼ばれ、
> 毎回新しいリストが作られます。Java で `= new ArrayList<>()` とするのと同じ意図です。

---

## 5. 処理フロー全体図

```
main()
 │
 ├─ build_parser()           # CLI 引数定義
 │
 ├─ ディレクトリ存在チェック・grep ファイル検出
 │
 └─ for grep_path in grep_files:          ← .grep ファイルを1つずつ処理
      │
      ├─ process_grep_file()              # 第1段階：直接参照の取得
      │    └─ parse_grep_line()           #   1行パース（不正行は None を返す）
      │         └─ classify_usage()      #   使用タイプ分類
      │               ├─ get_ast()       #     AST パース（キャッシュ付き）
      │               ├─ _classify_by_ast()  # AST ノードで判定
      │               └─ classify_usage_regex()  # 正規表現フォールバック
      │
      └─ for record in direct_records（定数/変数のみ）:
           │
           ├─ extract_variable_name()    # "String x = val;" → "x"
           ├─ determine_scope()          # project / class / method を判定
           │
           ├─ scope="project" → track_constant()
           │    └─ _search_in_lines()    # 全 .java ファイルを検索
           │
           ├─ scope="class"  → track_field()
           │    └─ _search_in_lines()    # 同一クラスファイル内を検索
           │    → find_getter_names()    # getter 候補を収集（命名規則 + AST）
           │    → track_getter_calls()   # getter 呼び出しをプロジェクト全体で検索
           │
           └─ scope="method" → _get_method_scope()（ブレースカウンタ）
                             → track_local()
                └─ _search_in_lines()    # 同一メソッド内を検索
      │
      └─ write_tsv()                     # TSV 出力（ソート済み・BOM付き）
 │
 └─ print_report()                       # サマリ表示
```

---

## 6. 段階①：CLI 起動（build_parser / main）

### build_parser

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Java grep結果 自動分類・使用箇所洗い出しツール"
    )
    parser.add_argument("--source-dir", required=True,
                        help="Javaソースコードのルートディレクトリ")
    parser.add_argument("--input-dir",  default="input",
                        help="grep結果ファイルの配置ディレクトリ（デフォルト: input/）")
    parser.add_argument("--output-dir", default="output",
                        help="TSV出力先ディレクトリ（デフォルト: output/）")
    return parser
```

Java の picocli・Commons CLI と同等です。`required=True` で必須引数、`default=` でデフォルト値を設定します。

> **なぜ `build_parser()` と `main()` を分けているのか**
>
> `main()` 内に argparse の定義を全部書いてしまうと、テストから引数を渡して
> パーサーを単体で検証できなくなります。分離することで
> `parser.parse_args(["--source-dir", "/tmp"])` と引数を直接渡すテストが書けます。

### main の構造

```python
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()       # sys.argv[1:] を解析してオブジェクトに変換

    source_dir = Path(args.source_dir)
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"エラー: ...", file=sys.stderr)
        sys.exit(1)

    grep_files = sorted(input_dir.glob("*.grep"))
    # Path.glob() は指定パターンにマッチするファイルをジェネレータで返す
    # sorted() でリストに変換しつつアルファベット順にソート

    if not grep_files:
        sys.exit(1)

    stats = ProcessStats()
    processed_files: list[str] = []

    try:
        for grep_path in grep_files:
            keyword = grep_path.stem
            # Path.stem = 拡張子を除いたファイル名
            # "input/SAMPLE.grep" の stem → "SAMPLE"

            direct_records = process_grep_file(grep_path, keyword, source_dir, stats)
            all_records: list[GrepRecord] = list(direct_records)
            # list(x) でコピーを作る（direct_records を変更せず、追跡結果を別途追加するため）

            for record in direct_records:
                # 定数定義・変数代入のみが間接追跡の起点になる
                if record.usage_type not in (
                    UsageType.CONSTANT.value, UsageType.VARIABLE.value
                ):
                    continue

                var_name = extract_variable_name(record.code, record.usage_type)
                if not var_name:
                    continue

                scope = determine_scope(
                    record.usage_type, record.code,
                    record.filepath, source_dir, int(record.lineno),
                )

                if scope == "project":
                    all_records.extend(
                        track_constant(var_name, source_dir, record, stats)
                    )
                elif scope == "class":
                    class_file = _resolve_java_file(record.filepath, source_dir)
                    if class_file:
                        all_records.extend(
                            track_field(var_name, class_file, record, source_dir, stats)
                        )
                        for getter_name in find_getter_names(var_name, class_file):
                            all_records.extend(
                                track_getter_calls(getter_name, source_dir, record, stats)
                            )
                elif scope == "method":
                    method_scope = _get_method_scope(
                        record.filepath, source_dir, int(record.lineno)
                    )
                    if method_scope:
                        all_records.extend(
                            track_local(var_name, method_scope, record, source_dir, stats)
                        )

            output_path = output_dir / f"{keyword}.tsv"
            write_tsv(all_records, output_path)
            processed_files.append(grep_path.name)

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    print_report(stats, processed_files)
```

> **なぜ間接追跡の起点を「定数定義・変数代入」に限定しているのか**
>
> 追跡が意味を持つのは「文言が別の名前に入れ替えられた（代入された）」場合だけです。
>
> ```java
> String code = "SAMPLE";           // ← 変数代入 → code という名前で追跡が必要
> if (x.equals("SAMPLE")) { ... }   // ← 条件判定 → 文言が直接使われているだけ、追跡不要
> return "SAMPLE";                   // ← return文  → 同上
> ```

---

## 7. 段階②：grep ファイルの読み込み（process_grep_file / parse_grep_line）

### parse_grep_line：1行のパース

grep の出力は `ファイルパス:行番号:コード行` という形式です。

```
tests/fixtures/java/Constants.java:9:    public static final String SAMPLE_CODE = "SAMPLE";
```

```python
def parse_grep_line(line: str) -> dict | None:
    stripped = line.rstrip('\n\r')
    # rstrip('\n\r') は末尾の改行文字のみ除去
    # strip() だと前後の空白も除去されてしまい、後のパース結果が変わる可能性があるため分けている

    if not stripped.strip():
        return None

    if _BINARY_PATTERN.match(stripped):   # "Binary file xxx matches" → スキップ
        return None

    # _GREP_LINE_PATTERN = re.compile(r':(\d+):')
    # () でキャプチャグループを作ると、split の結果にそのグループの値も含まれる
    parts = _GREP_LINE_PATTERN.split(stripped, maxsplit=1)

    if len(parts) != 3:
        return None

    filepath, lineno, code = parts   # 3変数同時代入（アンパック代入）

    return {
        "filepath": filepath,
        "lineno":   lineno,
        "code":     code.strip(),
    }
```

> **なぜ正規表現 `re.split(r':(\d+):', ...)` を使うのか（単純な `":"` 分割にしない理由）**
>
> 最もシンプルな実装は `line.split(":", 2)` ですが、**Windows パス**が問題になります。

**【具体例】Windows パスで `split(":", 2)` が失敗するケース**

```
入力行: C:\project\src\Foo.java:42:    String s = "SAMPLE";

split(":", 2) の結果（3分割）:
  ["C", "\\project\\src\\Foo.java", "42:    String s = ..."]
        ↑ "C" がファイルパスに、"\project\..." が行番号になってしまう

_GREP_LINE_PATTERN.split(..., maxsplit=1) の結果:
  ["C:\\project\\src\\Foo.java", "42", "    String s = ..."]
   ↑ ":42:" という「コロン＋数字＋コロン」だけで分割されるので正しく取れる
```

> さらに `maxsplit=1`（最初の1箇所だけ分割）を指定するのは、
> コード行の中に `:` が含まれる場合（三項演算子 `x ? a : b`、文字列リテラル `"a:b"` など）に
> それを区切り文字と誤認しないためです。

**【具体例】各入力に対する parse_grep_line の戻り値**

```
入力: "Foo.java:9:    String x = \"SAMPLE\";"
  → {"filepath": "Foo.java", "lineno": "9", "code": 'String x = "SAMPLE";'}

入力: ""  （空行）
  → None

入力: "Binary file logo.png matches"
  → None

入力: "no colon here"  （コロンなし）
  → None  (parts の長さが 3 にならないため)

入力: "Foo.java:9:    String x = \"a:b\";"  （コード内にコロン）
  → {"filepath": "Foo.java", "lineno": "9", "code": 'String x = "a:b";'}
  ※ maxsplit=1 なので 2番目以降の ":" は分割に使われない
```

> **なぜ `dict` を返すのか（`GrepRecord` を返さない理由）**
>
> この時点ではまだ「使用タイプ」が決まっておらず、`GrepRecord` を作れません。
> `classify_usage()` を呼んで使用タイプが決まってから初めて `GrepRecord` が生成されます。
> 中間の「パース結果」を表すために軽量な `dict` を使っています。

### process_grep_file：ファイル全体の処理

```python
def process_grep_file(path, keyword, source_dir, stats):
    records: list[GrepRecord] = []

    with open(path, encoding="utf-8", errors="replace") as f:
        # with ブロックは Java の try-with-resources に相当
        # ブロックを抜けると（例外があっても）自動でファイルが閉じる
        for line in f:             # ファイルオブジェクトは行ごとに読むイテレータ
            stats.total_lines += 1
            parsed = parse_grep_line(line)

            if parsed is None:
                stats.skipped_lines += 1
                continue

            usage_type = classify_usage(
                code=parsed["code"],
                filepath=parsed["filepath"],
                lineno=int(parsed["lineno"]),
                source_dir=source_dir,
                stats=stats,
            )

            records.append(GrepRecord(
                keyword=keyword,
                ref_type=RefType.DIRECT.value,
                usage_type=usage_type,
                filepath=parsed["filepath"],
                lineno=parsed["lineno"],
                code=parsed["code"],
            ))
            stats.valid_lines += 1

    return records
```

---

## 8. 段階③：使用タイプ分類（classify_usage / get_ast / _classify_by_ast）

コード行を「定数定義・条件判定・return 文...」など7種類のどれかに判定します。
まず AST（構文木）による精密判定を試み、失敗時のみ正規表現でフォールバックします。

### get_ast：Java ファイルを AST にパース（キャッシュ付き）

```python
_ast_cache: dict[str, object | None] = {}   # モジュールレベル変数（Java の static フィールド相当）

def get_ast(filepath: str, source_dir: Path) -> object | None:
    if not _JAVALANG_AVAILABLE:
        return None

    cache_key = str(filepath)
    if cache_key in _ast_cache:
        return _ast_cache[cache_key]

    candidate = Path(filepath)
    if not candidate.is_absolute():
        candidate = source_dir / filepath

    if not candidate.exists():
        _ast_cache[cache_key] = None
        return None

    try:
        source = candidate.read_text(encoding="shift_jis", errors="replace")
        tree = javalang.parse.parse(source)
        _ast_cache[cache_key] = tree
    except Exception:
        _ast_cache[cache_key] = None

    return _ast_cache[cache_key]
```

> **なぜ AST を使うのか（正規表現だけでは不十分な理由）**
>
> 正規表現はコード行の「文字列パターン」にしか反応できません。

**【具体例】正規表現が誤分類するケース**

```java
// パッケージプライベートフィールド（修飾子なし）
String type = "SAMPLE";
```

```
正規表現による判定:
  _FIELD_DECL_PATTERN にマッチしない（private/public などの修飾子がないため）
  → "method"（ローカル変数）と誤判定

AST による判定:
  このノードが FieldDeclaration（クラスメンバー）か LocalVariableDeclaration（ローカル変数）か
  を直接確認できる
  → "class"（フィールド）と正しく判定
```

> **なぜ Shift-JIS で読むのか**
>
> 古い Java プロジェクトのソースファイルはコメントや文字列リテラルに
> Shift-JIS が使われていることがあります。`errors="replace"` と組み合わせることで、
> 一部の文字が読めなくてもファイル全体のパースは続行できます。
> AST が目的のため、コメントや文字列の中身が少し化けても構文構造の解析には問題ありません。

### _classify_by_ast：AST ノードで種別を判定

javalang で解析した AST は「全ノードのイテレータ」として走査できます。
各ノードは「何行目に書かれているか」(`position.line`) を持っているので、
対象行のノードを探してその型で使用タイプを判定します。

```python
def _classify_by_ast(tree: object, lineno: int) -> str | None:
    for _, node in tree:
        # javalang の AST は (パス情報, ノード) のタプルを yield するジェネレータ
        # _ でパス情報を捨て、node だけ使う

        if not hasattr(node, 'position') or node.position is None:
            continue
        # hasattr() は Java の field != null チェックに相当
        # javalang のノードの中には position を持たないものもある（型パラメータなど）

        if node.position.line != lineno:
            continue

        if isinstance(node, javalang.tree.Annotation):
            return UsageType.ANNOTATION.value

        if isinstance(node, (javalang.tree.FieldDeclaration,
                              javalang.tree.LocalVariableDeclaration)):
            modifiers = getattr(node, 'modifiers', set()) or set()
            # getattr(obj, 'attr', default) は Java の
            # Optional.ofNullable(obj.getAttr()).orElse(default) に相当
            # さらに "or set()" は getattr が None を返した場合にも空セットにする
            if 'static' in modifiers and 'final' in modifiers:
                return UsageType.CONSTANT.value
            return UsageType.VARIABLE.value

        if isinstance(node, (javalang.tree.IfStatement,
                              javalang.tree.WhileStatement)):
            return UsageType.CONDITION.value

        if isinstance(node, javalang.tree.ReturnStatement):
            return UsageType.RETURN.value

        if isinstance(node, (javalang.tree.MethodInvocation,
                              javalang.tree.ClassCreator)):
            return UsageType.ARGUMENT.value

    return None
```

**【具体例】Constants.java の各行に対する AST 判定**

```java
// Constants.java（行番号付き）
 9:  public static final String SAMPLE_CODE = "SAMPLE";
13:  if (value.equals(SAMPLE_CODE)) {
21:  return SAMPLE_CODE;
```

```
lineno=9 のノード:
  FieldDeclaration, modifiers={"public", "static", "final"}
  "static" in modifiers AND "final" in modifiers → True
  → "定数定義"

lineno=13 のノード:
  IfStatement
  → "条件判定"

lineno=21 のノード:
  ReturnStatement
  → "return文"
```

> **なぜ `getattr(node, 'modifiers', set()) or set()` と二重にガードしているのか**
>
> `getattr(obj, 'attr', default)` は、属性が存在しない場合に `default` を返しますが、
> 属性は存在するが値が `None` という場合は `None` を返してしまいます。
> `'static' in None` はエラーになるため、`... or set()` で
> 「`None` が返ってきた場合も空セットにする」という二段構えのガードにしています。

### classify_usage：AST → 失敗時は正規表現

```python
def classify_usage(code, filepath, lineno, source_dir, stats):
    tree = get_ast(filepath, source_dir)

    if tree is None:
        # javalang はインストールされているのに失敗した場合のみ fallback_files に記録
        if _JAVALANG_AVAILABLE and filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)
        return classify_usage_regex(code)

    try:
        usage = _classify_by_ast(tree, lineno)
        if usage is not None:
            return usage
    except Exception:
        if filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)

    # AST にノードが見つからなかった（None が返った）場合も正規表現へ
    return classify_usage_regex(code)
```

**【具体例】AST が使えるかどうかによる分岐の全パターン**

```
ケース1: javalang がインストールされておらず _JAVALANG_AVAILABLE=False
  → get_ast() が即 None を返す → classify_usage_regex(code) を呼ぶ

ケース2: filepath のファイルが存在しない（grep 結果のパスが相対パスで解決できない）
  → get_ast() が None を返す（ファイル不在として None をキャッシュ）
  → fallback_files に filepath を追加 → classify_usage_regex(code) を呼ぶ

ケース3: ファイルは存在するが Java の構文エラー（独自拡張など）
  → javalang.parse.parse() が例外 → None をキャッシュ
  → fallback_files に filepath を追加 → classify_usage_regex(code) を呼ぶ

ケース4: AST は取得できたが対象行のノードが見つからない
  → _classify_by_ast() が None を返す → classify_usage_regex(code) を呼ぶ

ケース5: AST が取得でき、対象行のノードも見つかった（通常ケース）
  → _classify_by_ast() が UsageType.* を返す → そのまま返す
```

---

## 9. 段階④：間接参照の追跡（IndirectTracker 群）

変数代入・定数定義が見つかった場合、その変数/定数が「その後どこで使われているか」をさらに追跡します。

### extract_variable_name：変数名の抽出

```python
def extract_variable_name(code: str, usage_type: str) -> str | None:
    stripped = code.strip().rstrip(';')
    # rstrip(';') でセミコロンを除去（末尾にしかないため rstrip を使う）

    decl_part = stripped.split('=')[0].strip()
    # '=' で分割して左辺だけ取り出す
    # split('=') は Java の split("=") だが、最初の1文字だけでなくすべての = で分割する
    # [0] で最初の要素（= より前の部分）のみ取得

    tokens = decl_part.split()   # 空白で分割

    if len(tokens) >= 2:
        name = tokens[-1].strip('[];(){}<>')
        # tokens[-1] は最後のトークン（-1 = 末尾、Pythonの負インデックス）
        if name.isidentifier():
            return name
    return None
```

**【具体例】様々なコード行への適用結果**

```
入力: 'public static final String SAMPLE_CODE = "SAMPLE";'
  rstrip(';')   → 'public static final String SAMPLE_CODE = "SAMPLE"'
  split('=')[0] → 'public static final String SAMPLE_CODE '
  strip()       → 'public static final String SAMPLE_CODE'
  split()       → ["public", "static", "final", "String", "SAMPLE_CODE"]
  tokens[-1]    → "SAMPLE_CODE"
  isidentifier  → True
  戻り値: "SAMPLE_CODE"

入力: 'private String type = "SAMPLE";'
  rstrip(';')   → 'private String type = "SAMPLE"'
  split('=')[0] → 'private String type '
  tokens[-1]    → "type"
  戻り値: "type"

入力: 'private String type;'  （初期値なしの宣言）
  rstrip(';')   → 'private String type'
  split('=')[0] → 'private String type'  （= がないので全体）
  tokens[-1]    → "type"
  戻り値: "type"

入力: 'if (x.equals("SAMPLE")) {'  （条件判定行・変数宣言でない）
  rstrip(';')   → 'if (x.equals("SAMPLE")) {'
  split('=')[0] → 'if (x.equals("SAMPLE")) {'
  strip()       → 'if (x.equals("SAMPLE")) {'
  split()       → ["if", '(x.equals("SAMPLE"))', "{"]
  tokens[-1]    → "{"
  isidentifier("{") → False  ← '{' は識別子ではない
  戻り値: None  （変数名を抽出できなかった）
```

> **なぜ `rstrip(';')` が必要なのか**
>
> `rstrip` は末尾の文字だけを除去します（`strip` は前後両方）。
> セミコロンは宣言の末尾にしかないため `rstrip` で十分です。
> これがないと `'private String type;'.split()` の最後のトークンが `'type;'` になり、
> `'type;'.isidentifier()` が `False` を返して `None` になってしまいます。

### determine_scope：追跡範囲の決定

```python
def determine_scope(usage_type, code, filepath="", source_dir=None, lineno=0):
    if usage_type == UsageType.CONSTANT.value:
        return "project"

    if filepath and source_dir and lineno and _JAVALANG_AVAILABLE:
        tree = get_ast(filepath, source_dir)
        if tree is not None:
            try:
                for _, node in tree:
                    if not hasattr(node, 'position') or node.position is None:
                        continue
                    if node.position.line != lineno:
                        continue
                    if isinstance(node, javalang.tree.FieldDeclaration):
                        return "class"
                    if isinstance(node, javalang.tree.LocalVariableDeclaration):
                        return "method"
            except Exception:
                pass

    stripped = code.strip()
    if _FIELD_DECL_PATTERN.match(stripped):
        return "class"
    return "method"
```

**【具体例】3つのスコープとそれぞれの追跡範囲**

```java
// Constants.java
public class Constants {
    public static final String SAMPLE_CODE = "SAMPLE";  // ← "project" スコープ
    //   → プロジェクト全体の .java ファイルを検索
    //   → 理由: static final 定数は他クラスから参照できるため

    private String type = "SAMPLE";  // ← "class" スコープ
    //   → Constants.java 内だけを検索
    //   → 理由: フィールドは自クラスのメソッドからしか通常参照されないため

    public void process() {
        String msg = "SAMPLE";  // ← "method" スコープ
        //   → process() メソッド内（開始行〜終了行）だけを検索
        //   → 理由: ローカル変数はメソッド外からは参照不可のため
    }
}
```

> **なぜ正規表現フォールバックはパッケージプライベートフィールドを取りこぼすのか**
>
> `_FIELD_DECL_PATTERN` は先頭に `private|protected|public|static|final` がある前提です。
> パッケージプライベートフィールドは修飾子なしで書くため、
> 正規表現的にはローカル変数 `String type = ...` と区別がつきません。
> AST なら `FieldDeclaration` ノードか `LocalVariableDeclaration` ノードかを直接判別できます。

| スコープ | 判定条件 | 追跡先 |
|---|---|---|
| `project` | `static final` 定数 | ソースディレクトリ以下の全 `.java` ファイル |
| `class` | フィールド宣言（クラスメンバー）| 同一クラスファイルのみ |
| `method` | ローカル変数宣言 | 同一メソッドの行範囲内 |

### _search_in_lines：行リストから変数名を検索する共通ロジック

`track_constant`・`track_field`・`track_local` の全てが内部で使う共通関数です。

```python
def _search_in_lines(lines, var_name, start_line, origin, source_dir,
                     ref_type, stats, filepath_for_record):

    pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
    # \b は「単語境界」
    # re.escape() は Java の Pattern.quote() に相当

    records: list[GrepRecord] = []

    for idx, line in enumerate(lines):
        # enumerate(lines) は (インデックス, 値) のタプルを返す
        # Java の for (int idx = 0; idx < lines.size(); idx++) に相当
        current_lineno = start_line + idx

        # 変数の定義行自体はスキップ
        if (filepath_for_record == origin.filepath
                and str(current_lineno) == origin.lineno):
            continue

        if not pattern.search(line):
            continue

        code = line.strip()
        usage_type = classify_usage(...)
        records.append(GrepRecord(
            keyword=origin.keyword,
            ref_type=ref_type,
            ...
            src_var=var_name,
            src_file=origin.filepath,
            src_lineno=origin.lineno,
        ))

    return records
```

**【具体例】`\b` 単語境界が必要な理由**

```java
// var_name = "code" で検索するとき

String errorCode = "X";   // "code" が含まれるが単語の一部 → マッチしない ✓
String codeList  = "X";   // 同上 → マッチしない ✓
String code      = "X";   // "code" が単独の単語 → マッチする ✓
doSomething(code);        // 同上 → マッチする ✓
```

```
\b なし（r'code'）でマッチする行:
  errorCode, codeList, code, doSomething(code) ← 誤検出あり

\b あり（r'\bcode\b'）でマッチする行:
  code, doSomething(code)                      ← 正確
```

**【具体例】定義行スキップのしくみ**

```
origin.filepath = "Constants.java"
origin.lineno   = "9"

Constants.java の全行を走査中、current_lineno=9 の行に差し掛かったとき:
  filepath_for_record == origin.filepath → True
  str(9) == "9"                          → True
  → continue でスキップ
  （定数の定義行 "SAMPLE_CODE = ..." が間接参照として二重に出力されることを防ぐ）
```

### _get_method_scope：メソッドの行範囲を特定

```python
def _get_method_scope(filepath, source_dir, lineno):
    tree = get_ast(filepath, source_dir)
    if tree is None:
        return None

    # ① javalang でメソッドの開始行を全収集
    method_starts: list[int] = []
    for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
        if method_decl.position:
            method_starts.append(method_decl.position.line)

    method_starts.sort()

    # ② lineno 以下で最大の開始行 = lineno を含むメソッドの開始行
    method_start = None
    for start in method_starts:
        if start <= lineno:
            method_start = start   # 都度上書き → ループ終了時に lineno 直前の最大値

    if method_start is None:
        return None

    # ③ ブレースカウンタでメソッドの終了行を特定
    lines = java_file.read_text(...).splitlines()
    brace_count = 0
    found_open = False
    for i, line in enumerate(lines[method_start - 1:], start=method_start):
        brace_count += line.count('{') - line.count('}')
        if not found_open and brace_count > 0:
            found_open = True
        if found_open and brace_count <= 0:
            return (method_start, i)
    return None
```

> **なぜ javalang でメソッドの終了行を取得できないのか**
>
> javalang の AST ノードは「開始行（`position.line`）」しか保持していません。
> 終了行の情報は AST に含まれていないため、自前でテキストを解析する必要があります。

**【具体例】ブレースカウンタによる終了行特定の追跡**

```java
// Constants.java（method_start=12 の isSample メソッド）
12:  public static boolean isSample(String value) {  ← ここから走査開始
13:      if (value.equals(SAMPLE_CODE)) {
14:          return true;
15:      }
16:      return false;
17:  }   ← ここが終了
```

```
i=12: '{' が1個、'}' が0個 → brace_count = 1   found_open = true
i=13: '{' が1個、'}' が0個 → brace_count = 2
i=14: '{' が0個、'}' が0個 → brace_count = 2
i=15: '{' が0個、'}' が1個 → brace_count = 1
i=16: '{' が0個、'}' が0個 → brace_count = 1
i=17: '{' が0個、'}' が1個 → brace_count = 0   found_open=true かつ count≦0
  → return (12, 17)

結果: method_scope = (12, 17)
  = 12行目から17行目がこのメソッドの行範囲
```

> **`found_open` フラグが必要な理由**
>
> メソッドシグネチャより前の行（クラス宣言など）に `}` があり得るからです。
> `found_open` がないと、最初の `{` を見る前に `}` だけが出てきたとき（`brace_count ≦ 0`）に
> 誤ってそこが終了行と判断されます。
> 「最初の `{` を見た」という状態を `found_open` で記憶することで、
> メソッドボディの開始を確認してから終了判定を始めるようにしています。

---

## 10. 段階⑤：getter 経由参照の追跡（GetterTracker 群）

フィールドに getter があれば、getter の呼び出し元も「間接（getter経由）」として追跡します。

### find_getter_names：getter 候補を収集

```python
def find_getter_names(field_name: str, class_file: Path) -> list[str]:
    candidates: list[str] = []

    # 方式1: 命名規則（field_name="type" → "getType"）
    getter_by_convention = "get" + field_name[0].upper() + field_name[1:]
    # str[0]  : 先頭1文字
    # .upper(): 大文字化
    # str[1:] : 2文字目以降（Java の s.substring(1)）
    candidates.append(getter_by_convention)

    # 方式2: AST で `return field_name;` しているメソッドを検索
    if _JAVALANG_AVAILABLE:
        ...
        for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
            for _, stmt in method_decl.filter(javalang.tree.ReturnStatement):
                if (stmt.expression is not None
                        and hasattr(stmt.expression, 'member')
                        and stmt.expression.member == field_name):
                    candidates.append(method_decl.name)

    return list(set(candidates))
    # set() でリストの重複を除去してからリストに変換
```

**【具体例】Entity.java に対する find_getter_names の動作**

```java
// Entity.java
public class Entity {
    private String type = "SAMPLE";  // field_name = "type"

    public String getType() {        // ← 方式1（命名規則）と方式2（return type;）の両方でマッチ
        return type;
    }

    public String fetchCurrentType() {  // ← 方式2のみでマッチ（非標準命名）
        return type;
    }
}
```

```
方式1（命名規則）:
  "get" + "t".upper() + "ype" = "get" + "T" + "ype" = "getType"
  candidates = ["getType"]

方式2（AST の return 文解析）:
  getType()           の return 文: stmt.expression.member = "type" == field_name → 追加
  fetchCurrentType()  の return 文: stmt.expression.member = "type" == field_name → 追加
  candidates = ["getType", "getType", "fetchCurrentType"]

set() で重複除去:
  {"getType", "fetchCurrentType"}

list() でリストに変換:
  ["getType", "fetchCurrentType"]（順序は不定）
```

> **なぜ2つの方式を組み合わせるのか**
>
> 方式1（命名規則）だけでは、Java Bean 規約に従わない getter 名（例：`fetchType()`・`readType()`）
> を見逃します。方式2（return 文解析）では `return type;` しているメソッドを全て拾えるため、
> 非標準の命名にも対応できます。

> **なぜ false positive（誤検出）を許容しているのか**
>
> `track_getter_calls()` はプロジェクト内の同名のメソッド呼び出しを全て拾います。
> 例えば全く別のクラスが持つ `getType()` も検出されます。
> 設計方針として「見逃しより誤検出のほうが許容できる（漏れのない一覧を優先する）」
> という判断をしているため、これは仕様上許容された動作です。

### track_getter_calls：getter 呼び出し箇所を検索

```python
def track_getter_calls(getter_name, source_dir, origin, stats):
    pattern = re.compile(r'\b' + re.escape(getter_name) + r'\s*\(')
    # getter_name + '(' のパターン
    # \s* はメソッド名と '(' の間にスペースが入る可能性への対処

    for java_file in sorted(source_dir.rglob("*.java")):
        ...
        for i, line in enumerate(lines, start=1):
            # enumerate(lines, start=1) は 1 始まりのインデックスを生成
            if not pattern.search(line):
                continue
            records.append(GrepRecord(
                ref_type=RefType.GETTER.value,   # "間接（getter経由）"
                ...
            ))
```

**【具体例】Service.java での getter 呼び出し検出**

```java
// Service.java
public class Service {
    public void process(Entity entity) {
        if (entity.getType().equals("SAMPLE")) {  // ← getType() がマッチ
            System.out.println("matched");
        }
    }
}
```

```
getter_name = "getType"
pattern = r'\bgetType\s*\('

Service.java 10行目: "if (entity.getType().equals("SAMPLE")) {"
  pattern.search(line) → マッチ ✓
  → GrepRecord(ref_type="間接（getter経由）", filepath="Service.java", lineno="10", ...)
```

---

## 11. 段階⑥：TSV 出力（write_tsv）

```python
def write_tsv(records: list[GrepRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # output_path.parent : 出力ファイルの親ディレクトリ
    # mkdir(parents=True) : 中間ディレクトリも含めて作成（Java の Files.createDirectories() 相当）
    # exist_ok=True       : すでに存在してもエラーにしない

    sorted_records = sorted(
        records,
        key=lambda r: (r.keyword, r.filepath, int(r.lineno) if r.lineno.isdigit() else 0),
    )
    # sorted(iterable, key=関数) : key 関数の戻り値でソート
    # lambda r: ... : 無名関数（Java の r -> ... に相当）
    # タプル (a, b, c) を返すと「a が同値なら b を比較、b も同値なら c を比較」という複合ソート

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(_TSV_HEADERS)
        for r in sorted_records:
            writer.writerow([
                r.keyword, r.ref_type, r.usage_type, r.filepath,
                r.lineno, r.code, r.src_var, r.src_file, r.src_lineno,
            ])
```

> **なぜ行番号のソートに `int(r.lineno)` が必要なのか**

**【具体例】文字列ソートと数値ソートの違い**

```
ソート前（GrepRecord の lineno）: ["10", "2", "9", "1", "21"]

文字列ソート（デフォルト）:
  → ["1", "10", "2", "21", "9"]
  理由: "1" < "10" < "2"（先頭文字 "1" < "2" で比較されるため "10" が "2" より前）

数値ソート（int() 変換後）:
  → ["1", "2", "9", "10", "21"]
  理由: 1 < 2 < 9 < 10 < 21（数値として正しく比較）
```

`key=lambda r: (r.keyword, r.filepath, int(r.lineno) if r.lineno.isdigit() else 0)` は
「まずキーワードでソート、同じキーワードならファイルパスで、さらに同じなら行番号（数値）で」
という3段階の複合ソートキーです。

> **なぜ `encoding="utf-8-sig"` を使うのか（BOM の意味）**
>
> `utf-8-sig` は「UTF-8 + BOM（Byte Order Mark）」です。
> BOM は `EF BB BF` の3バイトをファイル先頭に付加します。
> これがないと Excel でファイルを開いたときに日本語が文字化けします
> （Excel が UTF-8 と認識しないため）。

> **なぜ `newline=""` が必要なのか**
>
> Python の `csv` モジュールは改行の処理を自分で管理します。
> `newline=""` を指定しないと、OS による改行変換が csv モジュールの処理と
> 二重にかかってしまい、`\r\r\n` のような二重改行が発生することがあります。

---

## 12. 段階⑦：処理サマリ表示（print_report）

```python
def print_report(stats: ProcessStats, processed_files: list[str]) -> None:
    print("\n--- 処理完了 ---")
    print(f"処理ファイル: {', '.join(processed_files)}")
    # str.join(iterable) : イテラブルの要素をセパレータで結合
    # Java の String.join(", ", list) と同じだが引数の順序が逆（区切り文字.join(リスト)）

    print(
        f"総行数: {stats.total_lines}  "
        f"有効: {stats.valid_lines}  "
        f"スキップ: {stats.skipped_lines}"
    )
    # 隣接する文字列リテラルは自動的に1つに連結される

    if stats.fallback_files:
        # Python ではリストが空のとき False、要素があるとき True と評価される
        # if stats.fallback_files: は Java の if (!list.isEmpty()) { に相当
        print(f"ASTフォールバック ({len(stats.fallback_files)} 件):")
        for f in stats.fallback_files:
            print(f"  {f}")

    if stats.encoding_errors:
        print(f"エンコーディングエラー ({len(stats.encoding_errors)} 件):")
        for f in stats.encoding_errors:
            print(f"  {f}")
```

---

## 13. AST キャッシュのしくみ

`_ast_cache` はモジュールレベルの辞書変数です。
Python のモジュールはプロセス起動時に1回だけロードされ、その後は同じオブジェクトが使い回されます。
これは Java の `static` フィールドと同等の寿命です。

```
                ┌──────────────────────────────────────────┐
                │  _ast_cache (dict)                        │
                │                                           │
                │  "Constants.java" → CompilationUnit  ←─ パース成功 │
                │  "Bad.java"       → None             ←─ パース失敗 or ファイル不在 │
                │  （未登録）        → キーが存在しない ←─ まだ試していない │
                └──────────────────────────────────────────┘
```

> **`dict.get()` ではなく `in` 演算子を使う理由**

**【具体例】`get()` と `in` の違い**

```python
cache = {}
cache["Bad.java"] = None   # パース失敗をキャッシュ済み

# .get() を使うと区別できない
cache.get("Bad.java")    # → None  ← パース失敗のキャッシュ
cache.get("Baz.java")    # → None  ← まだ試していない（キーが存在しない）
# どちらも None が返る → 「また試しに読みに行く」無駄な処理が発生してしまう

# in 演算子を使うと区別できる（Java の Map.containsKey() 相当）
"Bad.java" in cache    # → True   ← キャッシュ済み → 読みに行かない
"Baz.java" in cache    # → False  ← 未登録 → 初めて試みる
```

```python
# コード内の使われ方
cache_key = str(filepath)
if cache_key not in _ast_cache:          # ← 「まだ試していない」ときだけパースする
    try:
        tree = javalang.parse.parse(...)
        _ast_cache[cache_key] = tree
    except Exception:
        _ast_cache[cache_key] = None     # ← 失敗も記録（次回は即 None を返す）

return _ast_cache[cache_key]             # ← 成功なら tree、失敗なら None
```

---

## まとめ：処理の全体像（再確認）

```
main()
 │ CLI 引数パース → ディレクトリ検証 → .grep ファイル一覧取得
 ↓
for grep_path in *.grep:
 │
 ├─ process_grep_file()
 │   行ごとに parse_grep_line()
 │     ":数字:" で分割（Windows パス対応）→ {filepath, lineno, code} の dict
 │   → classify_usage()
 │       get_ast() でキャッシュ付き AST パース（Shift-JIS・失敗も None でキャッシュ）
 │       _classify_by_ast() で FieldDeclaration/ReturnStatement 等のノード型で判定
 │       判定できなければ classify_usage_regex() で正規表現フォールバック（優先度順）
 │   → 直接参照 GrepRecord のリスト
 │
 ├─ for record（定数定義・変数代入のみが起点）:
 │    extract_variable_name() → rstrip(';') → split('=')[0] → 最後のトークン
 │    determine_scope()       → AST で FieldDeclaration か LocalVariableDeclaration か判別
 │    ↓
 │    project → track_constant()   全 .java を rglob で走査
 │    class   → track_field()      同一クラスファイルのみ走査
 │              find_getter_names()（命名規則 + return 文 AST解析で getter 名収集）
 │              → track_getter_calls() プロジェクト全体で getter 呼び出しを検索
 │    method  → _get_method_scope()
 │                javalang でメソッド開始行収集 + ブレースカウンタで終了行を特定
 │              → track_local() メソッド行範囲のスライスのみ走査
 │
 │    各 track_*() の中核は _search_in_lines()
 │    （\b 単語境界マッチ・定義行スキップ・各行を再度 classify_usage で分類）
 │
 └─ write_tsv()
     int() 変換で数値ソート（"10"<"9" バグ防止）→ UTF-8 BOM 付き TSV に書き出し
 │
print_report()   統計・フォールバック発生ファイルを表示
```
