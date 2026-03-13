# analyze.py コード解説（Java経験者向け）

Python に不慣れな方向けに、Java との対比を交えながら analyze.py の全処理ロジックを解説します。
単純な箇所は簡潔に、難しい箇所・設計上の判断が必要な箇所は「**なぜそうなっているか**」を重点的に説明します。

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

Java プロジェクトを対象に、特定の文言（定数値など）を grep した結果ファイルを受け取り、**その文言がどのような文脈で使われているか**を自動分類して TSV に出力するツールです。

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
2. **間接参照**：変数・定数・フィールドに代入されていた場合、その変数の使用箇所を追跡
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
> `re.compile()` は正規表現の構文解析を行うため、わずかながらコストがかかります。
> 関数内に書くと、その関数が呼ばれるたびに毎回コンパイルが走ります。
> モジュールレベルに置くことで、プロセス起動時の1回だけコンパイルが実行されます。
> Java で `static final Pattern` にするのと同じ理由です。

> **優先度の仕組みと順序設計**
>
> リストの先頭から順番に評価し、最初にマッチしたラベルを返します。
> この順序が重要で、たとえば `return a.equals(CODE);` というコード行は
> `\breturn\b` にもマッチし、`.equals\s*\(` にもマッチします。
> `.equals` が先にリストに並んでいるため「条件判定」と分類されます。
> これは「`return` の中で比較しているならば、本質的な用途は条件判定」という
> 設計判断を優先度として表現したものです。

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

> **なぜ `frozen=True`（イミュータブル）にするのか**
>
> 1件のレコードは一度生成したら変更する必要がありません。
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
> print(stats2.fallback_files)  # → ["Foo.java"] ← 混入！
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
> `main()` 内に argparse の定義を全部書いてしまうと、テストから「--source-dir /tmp/src」の
> ような引数を渡してパーサーを単体で検証できなくなります。
> `build_parser()` を独立させることで、`parser.parse_args(["--source-dir", "/tmp"])` と
> 引数を直接渡すテストが書けます。

### main の構造

```python
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()       # sys.argv[1:] を解析してオブジェクトに変換

    source_dir = Path(args.source_dir)   # 文字列 → Path オブジェクト
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # ① ディレクトリ存在チェック
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"エラー: ...", file=sys.stderr)
        sys.exit(1)   # Java の System.exit(1) と同じ

    if not input_dir.exists() or not input_dir.is_dir():
        ...
        sys.exit(1)

    # ② .grep ファイルを検出
    grep_files = sorted(input_dir.glob("*.grep"))
    # Path.glob() は指定パターンにマッチするファイルをジェネレータで返す
    # sorted() でリストに変換しつつアルファベット順にソート

    if not grep_files:   # リストが空 → ファイルなし
        sys.exit(1)

    stats = ProcessStats()
    processed_files: list[str] = []

    try:
        for grep_path in grep_files:
            keyword = grep_path.stem
            # Path.stem = 拡張子を除いたファイル名
            # "input/SAMPLE.grep" → "SAMPLE"

            # 第1段階：直接参照
            direct_records = process_grep_file(grep_path, keyword, source_dir, stats)
            all_records: list[GrepRecord] = list(direct_records)
            # list(x) は Java の new ArrayList<>(x)（浅いコピーを作る）
            # コピーしておくことで、後の間接追跡結果をここに追加していける

            # 第2・第3段階：間接・getter 追跡
            for record in direct_records:
                # 定数定義・変数代入のみが間接追跡の起点になる
                # 条件判定・return文・メソッド引数などは変数に代入されていないので追跡不要
                if record.usage_type not in (
                    UsageType.CONSTANT.value, UsageType.VARIABLE.value
                ):
                    continue

                var_name = extract_variable_name(record.code, record.usage_type)
                if not var_name:   # 変数名を抽出できなかった場合はスキップ
                    continue

                scope = determine_scope(
                    record.usage_type, record.code,
                    record.filepath, source_dir, int(record.lineno),
                )

                if scope == "project":
                    all_records.extend(
                        track_constant(var_name, source_dir, record, stats)
                    )
                    # list.extend(other) は Java の list.addAll(other) に相当

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
            # Path / "文字列" は Java の path.resolve("文字列") に相当
            write_tsv(all_records, output_path)
            processed_files.append(grep_path.name)

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    print_report(stats, processed_files)
```

> **なぜ間接追跡の起点を「定数定義・変数代入」に限定しているのか**
>
> 他のタイプ（条件判定・return文・メソッド引数など）はすでに「文言を使っている現場」であり、
> そこから変数名を抽出してさらに追跡する意味がありません。
> 追跡が意味を持つのは「文言が別の名前に入れ替えられた（代入された）」場合だけです。
>
> 例：`String code = "SAMPLE"` → `code` という変数を通じてどこで使われるか？ → 追跡が必要
> 例：`if (x.equals("SAMPLE"))` → 文言が直接比較されているだけ → 追跡不要

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

    if not stripped.strip():        # 空白のみの行 → スキップ
        return None

    if _BINARY_PATTERN.match(stripped):   # "Binary file xxx matches" → スキップ
        return None

    # ":数字:" パターンで分割
    # _GREP_LINE_PATTERN = re.compile(r':(\d+):')
    # () でキャプチャグループを作ると、split の結果にそのグループの値も含まれる
    parts = _GREP_LINE_PATTERN.split(stripped, maxsplit=1)
    # "Foo.java:9:    code" → ["Foo.java", "9", "    code"]

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
>
> ```
> C:\project\src\Foo.java:42:    String s = "SAMPLE";
> ```
>
> これを `split(":", 2)` すると：
> ```
> ["C", "\\project\\src\\Foo.java", "42:    String s = ..."]
>            ↑ "C" がファイルパスになってしまう
> ```
>
> `:数字:` のパターンは「行番号を囲んでいるコロン」だけにマッチします。
> `C:` は `:C:` でも `:42:` でもないのでマッチせず、正しく分割されます。
>
> さらに `maxsplit=1`（最初の1箇所だけ分割）を指定するのは、
> コード行の中に `:` が含まれている場合（例：三項演算子、文字列リテラル）に
> それを区切り文字と誤認しないためです。

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
    if cache_key in _ast_cache:         # キャッシュヒット → 再パース不要
        return _ast_cache[cache_key]

    candidate = Path(filepath)
    if not candidate.is_absolute():
        candidate = source_dir / filepath   # 相対パス → ソースルートからのパスに変換

    if not candidate.exists():
        _ast_cache[cache_key] = None        # 「試みたが存在しなかった」をキャッシュ
        return None

    try:
        source = candidate.read_text(encoding="shift_jis", errors="replace")
        # Javaソースに Shift-JIS が含まれていても読めるようにするため
        # errors="replace" → 読めない文字は U+FFFD（?に似た文字）に置換して続行
        tree = javalang.parse.parse(source)
        _ast_cache[cache_key] = tree
    except Exception:
        # javalang.parser.JavaSyntaxError を含む全ての例外を「フォールバック扱い」にする
        _ast_cache[cache_key] = None

    return _ast_cache[cache_key]
```

> **なぜ AST を使うのか（正規表現だけでは不十分な理由）**
>
> 正規表現はコード行の「文字列パターン」にしか反応できません。
> 例として `private String type = "SAMPLE";` を考えます。
> - `private` がついていれば正規表現でもフィールドと判定できます。
> - しかし **パッケージプライベート**（修飾子なし）の `String type = "SAMPLE";` は
>   ローカル変数宣言と区別できません（同じ構文になるため）。
>
> AST ならば `FieldDeclaration` ノードか `LocalVariableDeclaration` ノードかを直接判別できます。
>
> 一方、正規表現のフォールバックも残している理由は、`javalang` が未インストールの環境や、
> パースできない Java ファイル（javadoc の独自拡張構文など）に対応するためです。

> **なぜ Shift-JIS で読むのか**
>
> 古い Java プロジェクトのソースファイルはコメントや文字列リテラルに
> Shift-JIS が使われていることがあります。`errors="replace"` と組み合わせることで、
> 一部の文字が読めなくてもファイル全体のパースは続行できます。
> AST が目的のため、コメントや文字列の中身が少し化けても
> 構文構造の解析には問題ありません。

> **なぜ `None` もキャッシュするのか**
>
> 「ファイルが存在しない」や「パースに失敗した」という結果もキャッシュします。
> そうしないと、同じ .grep ファイル内の同じ Java ファイルへの参照が100行あれば
> 100回「ファイルを探してみたが見つからなかった」という無駄な処理が走ります。

### _classify_by_ast：AST ノードで種別を判定

```python
def _classify_by_ast(tree: object, lineno: int) -> str | None:
    for _, node in tree:
        # javalang の AST は (パス情報, ノード) のタプルを延々と yield するジェネレータ
        # _ でパス情報を捨て、node だけ使う（Java には相当する構文なし）

        if not hasattr(node, 'position') or node.position is None:
            continue
        # hasattr() は Java の obj != null && obj.hasField() に相当する安全チェック
        # javalang のノードの中には position を持たないものもある（例：型パラメータ）

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
            # （javalang では modifiers が None になるケースがある）
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

    return None   # 対象行のノードが見つからない → 呼び出し元が正規表現フォールバックへ
```

> **なぜ `getattr(node, 'modifiers', set()) or set()` と二重にガードしているのか**
>
> `getattr(obj, 'attr', default)` は、属性が存在しない場合に `default` を返します。
> しかし javalang では属性は存在するが値が `None` という場合もあります（修飾子なしのフィールドなど）。
> `getattr(..., set())` だけでは `None` が返ってくる可能性があり、
> `'static' in None` はエラーになります。
> `... or set()` を追加することで「`None` を返してきた場合も空セットにする」という
> 二段構えのガードになっています。

### classify_usage：AST → 失敗時は正規表現

```python
def classify_usage(code, filepath, lineno, source_dir, stats):
    tree = get_ast(filepath, source_dir)

    if tree is None:
        # AST が使えない → 正規表現フォールバック
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

> **なぜ「AST で判定できなかった場合」に正規表現フォールバックがあるのか**
>
> javalang は全ての構文要素に行番号を付与しているわけではありません。
> 例えば `for` 文の中のインクリメント式などは `position` が `None` になります。
> `_classify_by_ast()` が `None` を返した場合（= 対象行のノードが見つからなかった）は、
> 正規表現が最後の手段として使われます。これにより、AST が使えても使えなくても
> 必ず何らかの分類結果が返るようになっています。

### classify_usage_regex：正規表現フォールバック

```python
def classify_usage_regex(code: str) -> str:
    stripped = code.strip()
    for pattern, usage_type in USAGE_PATTERNS:
        if pattern.search(stripped):   # search() はコード行の任意位置でマッチを探す
            return usage_type          # マッチしたら即 return（残りはチェックしない）
    return UsageType.OTHER.value
```

`pattern.search()` は Java の `Matcher.find()` に相当します（コード行のどこかにパターンがあればマッチ）。
`pattern.match()` だと先頭からしか検索しません（Java の `Matcher.matches()` に近い）。

---

## 9. 段階④：間接参照の追跡（IndirectTracker 群）

変数代入・定数定義が見つかった場合、その変数/定数が「その後どこで使われているか」をさらに追跡します。

### extract_variable_name：変数名の抽出

```python
def extract_variable_name(code: str, usage_type: str) -> str | None:
    stripped = code.strip().rstrip(';')
    # rstrip(';') でセミコロンを除去
    # なぜ rstrip か：セミコロンは末尾にしかないため。strip(';') だと先頭も対象になる。

    decl_part = stripped.split('=')[0].strip()
    # '=' で分割して左辺だけ取り出す
    # split('=') は Java の split("=") だが、最初の1文字だけでなくすべての = で分割する
    # [0] で最初の要素（= より前の部分）のみ取得
    #
    # 例1: 'public static final String SAMPLE_CODE = "SAMPLE"'
    #   split('=')[0] → 'public static final String SAMPLE_CODE '
    #   strip()       → 'public static final String SAMPLE_CODE'
    #
    # 例2: 'private String type;' （セミコロンのみで = がない場合）
    #   rstrip(';')   → 'private String type'
    #   split('=')[0] → 'private String type'（= がないので全体がそのまま）

    tokens = decl_part.split()
    # 空白で分割 → ["public", "static", "final", "String", "SAMPLE_CODE"]

    if len(tokens) >= 2:
        # トークンが1つしかない（型名だけなど）は変数宣言ではないと判断してスキップ
        name = tokens[-1].strip('[];(){}<>')
        # tokens[-1] は最後のトークン（Pythonの負インデックス：-1 = 末尾）
        # 配列型 "String[]" → strip で '[]' を除去 → "String" にならないよう strip する
        if name.isidentifier():
            # isidentifier() = 有効な識別子か（英数字・アンダースコアのみ、数字始まりでない）
            return name
    return None
```

> **なぜ `rstrip(';')` が必要なのか**
>
> `private String type;` のようなフィールド宣言（初期値なしの `;` で終わる形）を扱うためです。
> これを `split('=')` すると `['private String type;']` となり、`[0]` が `'private String type;'` で、
> その最後のトークンが `'type;'` になってしまいます。
> `rstrip(';')` で先にセミコロンを除去しておくことで正しく `'type'` が取れます。

### determine_scope：追跡範囲の決定

```python
def determine_scope(usage_type, code, filepath="", source_dir=None, lineno=0):
    if usage_type == UsageType.CONSTANT.value:
        return "project"
        # static final の定数はクラス外からも参照できるためプロジェクト全体が対象

    # AST が使えるなら FieldDeclaration / LocalVariableDeclaration ノードで判定
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
                        return "class"    # クラスフィールド → 同一クラスが対象
                    if isinstance(node, javalang.tree.LocalVariableDeclaration):
                        return "method"   # ローカル変数 → 同一メソッドが対象
            except Exception:
                pass

    # AST が使えない場合：正規表現フォールバック
    # _FIELD_DECL_PATTERN = r'^(private|protected|public|static|final|\s)*\s+型名 変数名'
    stripped = code.strip()
    if _FIELD_DECL_PATTERN.match(stripped):
        return "class"
    return "method"
```

> **なぜ正規表現フォールバックはパッケージプライベートフィールドを取りこぼすのか**
>
> `_FIELD_DECL_PATTERN` は先頭に `private|protected|public|static|final` がある前提で
> 書かれています。パッケージプライベートフィールドは修飾子なしで書くため：
>
> ```java
> String type = "SAMPLE";   // ← パッケージプライベートフィールド
> ```
>
> これは正規表現的にはローカル変数 `String type = ...` と区別がつきません。
> どちらも「型名 変数名 = 値」という同じ構文だからです。
> このケースを正しく処理するには AST で「このノードがクラス直下にある FieldDeclaration か」を
> 確認する必要があります。それが AST 判定を優先する理由です。

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
    # \b は「単語境界」。var_name が "MY_VAR" のとき：
    #   "MY_VAR = 1"    → マッチ ✓
    #   "MY_VARIABLE"   → マッチしない ✓（"MY_VAR" が単語の途中で終わっていないため）
    #   "prefix_MY_VAR" → マッチしない ✓（単語の先頭が "_" の後ろのため）
    #
    # re.escape() は Java の Pattern.quote() に相当
    # var_name に正規表現の特殊文字（例：$）が含まれていても安全にマッチできる

    records: list[GrepRecord] = []

    for idx, line in enumerate(lines):
        # enumerate(lines) は (インデックス, 値) のタプルを返す
        # Java の for (int i = 0; i < lines.size(); i++) に相当
        current_lineno = start_line + idx

        # 変数の定義行自体はスキップ
        # （"SAMPLE_CODE = ..." という定義行が間接参照としてまた出てくることを防ぐ）
        if (filepath_for_record == origin.filepath
                and str(current_lineno) == origin.lineno):
            continue

        if not pattern.search(line):
            continue

        code = line.strip()
        usage_type = classify_usage(   # 間接参照先の行も使用タイプを分類
            code=code,
            filepath=filepath_for_record,
            lineno=current_lineno,
            source_dir=source_dir,
            stats=stats,
        )
        records.append(GrepRecord(
            keyword=origin.keyword,
            ref_type=ref_type,          # "間接" or "間接（getter経由）"
            usage_type=usage_type,
            filepath=filepath_for_record,
            lineno=str(current_lineno),
            code=code,
            src_var=var_name,           # 経由した変数/定数名
            src_file=origin.filepath,   # 変数が定義されたファイル
            src_lineno=origin.lineno,   # 変数が定義された行
        ))

    return records
```

> **なぜ `\b`（単語境界）を使うのか**
>
> 変数名 `code` で検索するとき、`\b` なしの正規表現だと
> `errorCode`・`codeList` などにもマッチしてしまいます。
> `\b` は英数字とそれ以外の境界を示すため、`code` は「単体の単語として登場している箇所」
> だけにマッチします。

### track_constant：プロジェクト全体を検索

```python
def track_constant(var_name, source_dir, origin, stats):
    records: list[GrepRecord] = []

    for java_file in sorted(source_dir.rglob("*.java")):
        # rglob("*.java") = 再帰的にサブディレクトリも含めて *.java を全検索
        # Java の Files.walk(source_dir).filter(p -> p.toString().endsWith(".java")) に相当
        # sorted() で処理順を安定させる（OS によってファイル列挙順が変わるため）
        try:
            lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
            # read_text() : ファイル全体を1つの文字列として読む
            # splitlines() : 改行で分割してリストにする（Java の Files.readAllLines() 相当）
        except Exception:
            stats.encoding_errors.append(str(java_file))
            continue   # 読めないファイルはスキップして次へ

        records.extend(_search_in_lines(
            lines=lines, var_name=var_name, start_line=1,
            origin=origin, source_dir=source_dir,
            ref_type=RefType.INDIRECT.value,
            stats=stats,
            filepath_for_record=str(java_file),
        ))

    return records
```

> **なぜ `sorted()` するのか**
>
> `rglob()` が返すファイルの順序はプラットフォームによって異なります（Linux は inode 順、
> Windows はアルファベット順、など）。`sorted()` で常に同じ順に処理することで、
> 出力 TSV の行順が実行環境によってバラバラになることを防ぎます。

### _get_method_scope：メソッドの行範囲を特定

```python
def _get_method_scope(filepath, source_dir, lineno):
    tree = get_ast(filepath, source_dir)
    if tree is None:
        return None

    # ① javalang でメソッドの開始行を全収集
    method_starts: list[int] = []
    for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
        # tree.filter(NodeType) は特定の型のノードだけを抽出するヘルパー
        if method_decl.position:
            method_starts.append(method_decl.position.line)

    method_starts.sort()   # 昇順ソート（Javaの Collections.sort() 相当）

    # ② lineno 以下で最大の開始行 = lineno を含むメソッドの開始行
    method_start = None
    for start in method_starts:
        if start <= lineno:
            method_start = start   # 都度上書き → ループ終了時に lineno 直前の最大値

    if method_start is None:
        return None   # メソッドより前の行（クラス宣言など）

    # ③ ブレースカウンタでメソッドの終了行を特定
    java_file = _resolve_java_file(filepath, source_dir)
    lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()

    brace_count = 0
    found_open = False
    for i, line in enumerate(lines[method_start - 1:], start=method_start):
        # lines[method_start - 1:] : メソッド開始行から末尾までのスライス
        # enumerate(..., start=method_start) : ループ変数 i が method_start から始まる

        brace_count += line.count('{') - line.count('}')
        if not found_open and brace_count > 0:
            found_open = True   # 最初の '{' を発見
        if found_open and brace_count <= 0:
            return (method_start, i)   # ブレースが全て閉じた行 = メソッド終了

    return None
```

> **なぜ javalang でメソッドの終了行を取得できないのか**
>
> javalang の AST ノードは「開始行（`position.line`）」しか保持していません。
> 終了行の情報は AST に含まれていないため、自前でテキストを解析する必要があります。
>
> ブレースカウンタ方式は「`{` を見つけるたびに +1、`}` を見つけるたびに -1、
> 最初の `{` を見た後に 0 になった行がメソッドの終わり」という方式です。
> `found_open` フラグが必要な理由は、メソッドシグネチャ行（例：`public void run() {`）に
> `{` があってもすぐには終了しないため「最初の `{` を見た」という状態を記憶するためです。
>
> ```java
> public void method() {    // brace_count: 0→1, found_open: true
>     if (x) {              // brace_count: 1→2
>         doSomething();
>     }                     // brace_count: 2→1
> }                         // brace_count: 1→0, found_open かつ count≦0 → ここが終了行
> ```

### track_local：ローカル変数の追跡

```python
def track_local(var_name, method_scope, origin, source_dir, stats):
    java_file = _resolve_java_file(origin.filepath, source_dir)
    if java_file is None:
        return []

    all_lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()

    start_line, end_line = method_scope   # タプルのアンパック代入
    # start_line, end_line = (12, 17) のような代入

    method_lines = all_lines[start_line - 1 : end_line]
    # Pythonのリストスライス: list[a:b] は インデックス a 以上 b 未満（0-indexed）
    # start_line が 1-indexed なので -1 してゼロベースに変換
    # end_line はそのまま使うと「その行を含む」スライスになる（b は含まれないため）
    #
    # 例: start_line=12, end_line=17 のとき
    #   all_lines[11:17] → インデックス 11,12,13,14,15,16 の6行 = 12行目〜17行目

    return _search_in_lines(
        lines=method_lines,
        var_name=var_name,
        start_line=start_line,   # 検索結果の行番号をファイル全体での行番号に変換するために必要
        origin=origin,
        ...
    )
```

---

## 10. 段階⑤：getter 経由参照の追跡（GetterTracker 群）

フィールドに getter があれば、getter の呼び出し元も「間接（getter経由）」として追跡します。

### find_getter_names：getter 候補を収集

```python
def find_getter_names(field_name: str, class_file: Path) -> list[str]:
    candidates: list[str] = []

    # 方式1: 命名規則（field_name="type" → "getType"）
    getter_by_convention = "get" + field_name[0].upper() + field_name[1:]
    # str[0]    : 先頭1文字 → .upper() で大文字化
    # str[1:]   : 2文字目以降（Javaの s.substring(1) に相当）
    # "type" → "g" + "e" + "t" + "T" + "ype" → "getType"
    candidates.append(getter_by_convention)

    # 方式2: AST で `return field_name;` しているメソッドを検索（非標準命名に対応）
    if _JAVALANG_AVAILABLE:
        cache_key = str(class_file)
        if cache_key not in _ast_cache:
            # まだキャッシュされていなければここでパース
            try:
                source = class_file.read_text(encoding="shift_jis", errors="replace")
                _ast_cache[cache_key] = javalang.parse.parse(source)
            except Exception:
                _ast_cache[cache_key] = None

        tree = _ast_cache[cache_key]
        if tree is not None:
            for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
                for _, stmt in method_decl.filter(javalang.tree.ReturnStatement):
                    if (stmt.expression is not None
                            and hasattr(stmt.expression, 'member')
                            and stmt.expression.member == field_name):
                        candidates.append(method_decl.name)

    return list(set(candidates))
    # set() でリストの重複を除去してからリストに戻す
    # 命名規則と AST 解析で同じ名前が見つかった場合のために必要
```

> **なぜ2つの方式を組み合わせるのか**
>
> 方式1（命名規則）だけでは、Java Bean 規約に従わない getter 名（例：`fetchType()`・`readType()`）
> を見逃します。方式2（return 文解析）では `return type;` しているメソッドを全て拾えるため、
> 非標準の命名にも対応できます。ただし方式2は `javalang` が必要なので、
> インストールされていない場合は方式1だけで動作します。

> **なぜ false positive（誤検出）を許容しているのか**
>
> `track_getter_calls()` はプロジェクト内の同名のメソッド呼び出しを全て拾います。
> 例えば `getType()` という名前を持つ他のクラスのメソッドも検出されます。
> ツールの設計方針として「見逃しより誤検出のほうが許容できる」という判断です。
> 調査目的では漏れのない一覧のほうが有用で、人手でノイズを除くコストは低いためです。

### track_getter_calls：getter 呼び出し箇所を検索

```python
def track_getter_calls(getter_name, source_dir, origin, stats):
    pattern = re.compile(r'\b' + re.escape(getter_name) + r'\s*\(')
    # getter_name + '(' のパターン
    # \s* はメソッド名と '(' の間にスペースが入る可能性への対処（例：getType ()）

    for java_file in sorted(source_dir.rglob("*.java")):
        lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()

        for i, line in enumerate(lines, start=1):
            # enumerate(lines, start=1) は 1 始まりのインデックスを生成
            # デフォルトは 0 始まりだが start= で変更できる
            if not pattern.search(line):
                continue
            records.append(GrepRecord(
                ref_type=RefType.GETTER.value,   # "間接（getter経由）"
                ...
            ))
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
    # sorted(iterable, key=関数) : key 関数の戻り値でソート（Java の Comparator に相当）
    # lambda r: ... : 無名関数（Java の r -> ... に相当）
    # タプル (a, b, c) を返すと「a が同値なら b を比較、b も同値なら c を比較」という複合ソート
    # int(r.lineno) : 文字列を整数に変換して数値ソート

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
>
> 行番号は文字列で保持しています（`lineno: str`）。
> 文字列のままソートすると辞書順（アルファベット順）になります：
>
> ```
> 文字列ソート: "10" < "2" < "9"  ← "1" が "2" より前なので誤った順序
> 数値ソート:   2 < 9 < 10        ← 正しい順序
> ```
>
> `int(r.lineno)` で整数に変換してソートキーにすることで正しい数値順になります。
> `if r.lineno.isdigit() else 0` は、万が一行番号が数字でない文字列だった場合の安全策です。

> **なぜ `encoding="utf-8-sig"` を使うのか（BOM の意味）**
>
> `utf-8-sig` は「UTF-8 + BOM（Byte Order Mark）」です。
> BOM は `EF BB BF` の3バイトをファイル先頭に付加します。
> これがないと Excel でファイルを開いたときに日本語が文字化けします
> （Excel が UTF-8 と認識しないため）。
> テキストエディタや Python での再読み込みでは BOM は自動的に無視されるため
> 互換性の問題はありません。

> **なぜ `newline=""` が必要なのか**
>
> Python の `csv` モジュールは改行の処理を自分で管理します。
> `newline=""` を指定しないと、OS によって改行コードが変換され（Windows では `\r\n`、
> Linux では `\n`）、csv モジュールがその変換済みの改行をさらに変換して
> `\r\r\n` のような二重改行が発生することがあります。
> `newline=""` で「OS による改行変換を無効化」して csv モジュールに制御を渡します。

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
    # 隣接する文字列リテラルは自動的に1つに連結される（Java の + 演算子と同じ結果）

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
                ┌──────────────────────────────────────┐
                │  _ast_cache (dict)                    │
                │                                       │
                │  "Foo.java" → CompilationUnit  ←─ パース成功 │
                │  "Bar.java" → None             ←─ パース失敗 or ファイル不在 │
                │  （未登録）  → キーが存在しない ←─ まだ試していない │
                └──────────────────────────────────────┘
```

> **`dict.get()` ではなく `in` 演算子を使う理由**
>
> Python の `dict.get(key)` は「キーが存在しない場合」も「値が `None` の場合」も
> 同じく `None` を返します。この2つを区別できません。
>
> ```python
> cache = {"Bar.java": None}   # パース失敗を記録済み
>
> cache.get("Bar.java")    # → None  ← パース失敗のキャッシュ
> cache.get("Baz.java")    # → None  ← まだ試していない
> # 両方 None が返るため区別できない
>
> "Bar.java" in cache      # → True   ← キャッシュ済み（パース失敗）
> "Baz.java" in cache      # → False  ← まだ試していない
> # in 演算子なら区別できる
> ```
>
> Java の `Map.containsKey()` に相当します。
> 「`None` を入れた（試みたが失敗）」と「未登録（まだ試していない）」を区別することで、
> 存在しないファイルへの無駄なアクセスを確実に防ぎます。

---

## まとめ：処理の全体像（再確認）

```
main()
 │ CLI 引数パース → ディレクトリ検証 → .grep ファイル一覧取得
 ↓
for grep_path in *.grep:
 │
 ├─ process_grep_file()
 │   行ごとに parse_grep_line()（filepath:lineno:code に分割）
 │           → classify_usage()（AST優先 → 正規表現フォールバックで7種分類）
 │   → 直接参照 GrepRecord のリスト
 │
 ├─ for record（定数定義・変数代入のみが起点）:
 │    extract_variable_name() → "String x = val;" から "x" を取り出す
 │    determine_scope()       → AST で FieldDeclaration / LocalVariable を判別
 │    ↓
 │    project → track_constant()   全 .java を rglob で走査
 │    class   → track_field()      同一クラスファイルのみ走査
 │              find_getter_names()（命名規則 + return 文 AST解析）
 │              → track_getter_calls() プロジェクト全体で getter 呼び出しを検索
 │    method  → _get_method_scope()（AST で開始行 + ブレースカウンタで終了行）
 │              → track_local() メソッド行範囲のみ走査
 │
 │    各 track_*() の中核は _search_in_lines()
 │    （\b で単語境界マッチ・定義行スキップ・各行を再度 classify_usage で分類）
 │
 └─ write_tsv()
     数値ソート（文字列ソート "10"<"9" バグ防止）→ UTF-8 BOM 付き TSV に書き出し
 │
print_report()   統計・フォールバック発生ファイルを表示
```
