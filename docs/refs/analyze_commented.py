"""Java grep結果 自動分類・使用箇所洗い出しツール（超詳細コメント版）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【このツールが何をするか】

Javaプロジェクト内に存在する特定の文言（例: "SAMPLE"）を grep した結果ファイルを受け取り、
「その文言がどんな文脈で使われているか」を自動分類して TSV ファイルに出力します。

【処理の3段階】

  ステップ1 ─ 直接参照の分類
    grep ファイルの各行を読み込み、コード行が「定数定義」なのか「条件判定」なのか
    「return 文」なのかを AST（構文木）で判定する。

  ステップ2 ─ 間接参照の追跡
    ステップ1 で「定数定義」「変数代入」と判定された行から変数名を抽出し、
    その変数がプロジェクト内のどこで使われているかを再検索する。

  ステップ3 ─ getter 経由参照の追跡
    ステップ2 でフィールド（クラスの属性）だと判明した変数については、
    対応する getter メソッド（getXxx 等）の呼び出し箇所もあわせて探す。

【入出力イメージ】

  input/SAMPLE.grep:
    tests/fixtures/java/Constants.java:9:    public static final String SAMPLE_CODE = "SAMPLE";
    tests/fixtures/java/Constants.java:13:        if (value.equals(SAMPLE_CODE)) {
    tests/fixtures/java/Entity.java:8:    private String type = "SAMPLE";

  output/SAMPLE.tsv:
    文言    参照種別          使用タイプ  ファイル          行  コード行
    SAMPLE  直接              定数定義    Constants.java    9   public static final ...
    SAMPLE  直接              条件判定    Constants.java    13  if (value.equals ...
    SAMPLE  間接              条件判定    Constants.java    13  if (value.equals ...  ← SAMPLE_CODE 経由
    SAMPLE  間接（getter経由）条件判定    Service.java      10  if (entity.getType()... ← getter 経由

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
# Python 3.10 未満でも `str | None` のような Union 型注釈を使えるようにする。
# これがないと古いバージョンの Python で SyntaxError になる。
from __future__ import annotations

# ─── 標準ライブラリ ──────────────────────────────────────────────────────────
import argparse   # CLI オプション（--source-dir 等）の解析に使う
import csv        # TSV（タブ区切り）ファイルの書き出しに使う
import re         # 正規表現。パターンマッチングによる文字列解析に使う
import sys        # sys.exit()（プログラムの終了）や sys.stderr（エラー出力）に使う
from dataclasses import dataclass, field  # データクラスの定義に使う
from enum import Enum                     # 列挙型の定義に使う
from pathlib import Path                  # ファイルパスをオブジェクトとして扱うためのクラス

# ─── サードパーティライブラリ（オプション）────────────────────────────────────
# javalang は Java の AST（抽象構文木）パーサ。
# pip でインストールするサードパーティ製ライブラリのため、
# インストールされていない環境でも動作できるよう try/except で囲む。
# → インストールされていれば AST による精密な判定を行う。
# → インストールされていなければ正規表現による近似判定にフォールバックする。
try:
    import javalang
    _JAVALANG_AVAILABLE = True   # AST 解析が使える状態フラグ
except ImportError:
    # javalang が入っていない場合は False にして後続処理でスキップ
    _JAVALANG_AVAILABLE = False


# ============================================================================
# 定数（モジュールレベル変数）
# ============================================================================
#
# 【なぜモジュールレベルに置くのか】
#   正規表現の re.compile() はパターン文字列の構文解析を行うためコストが掛かる。
#   関数内に書くと「その関数が呼ばれるたびに毎回コンパイル」が走る。
#   モジュールレベルに置くことで「プロセス起動時の1回だけ」で済む。
#   Java の `static final Pattern` と同じ理由。
# ============================================================================

# 使用タイプ分類パターン（優先度順リスト）
#
# 型の読み方: list[tuple[re.Pattern, str]]
#   = (コンパイル済み正規表現, 分類ラベル) のペアを並べたリスト
#
# 【優先度の仕組み】
#   後述の classify_usage_regex() がこのリストを先頭から順に評価し、
#   最初にマッチしたラベルを返す。
#   → リストの順序 = 優先度。「アノテーション」が最優先、「メソッド引数」が最後尾。
#
# 【優先度設計の根拠（例）】
#   "return a.equals(CODE);" は \breturn\b にも \.equals\s*\( にもマッチする。
#   条件判定パターン（優先度3）が return 文パターン（優先度4）より先に来るため、
#   「比較している」という本質的な意味が「return している」より優先される。
USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 優先度1: アノテーション (@Xxx(...) の形)
    #   例: @RequestMapping("SAMPLE")、@Column(name = "SAMPLE")
    (re.compile(r'@\w+\s*\('),                                  "アノテーション"),

    # 優先度2: 定数定義 (static final が含まれる行)
    #   例: public static final String CODE = "SAMPLE";
    (re.compile(r'\bstatic\s+final\b'),                         "定数定義"),

    # 優先度3: 条件判定 (if/while/equals/.equals/!=/== を含む行)
    #   例: if (x.equals("SAMPLE")) { ... }
    #   例: while (code != "SAMPLE") { ... }
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\.equals\s*\(|[!=]='), "条件判定"),

    # 優先度4: return 文 (return キーワードを含む行)
    #   例: return "SAMPLE";
    (re.compile(r'\breturn\b'),                                  "return文"),

    # 優先度5: 変数代入 ("型名 変数名 =" の形)
    #   例: String msg = "SAMPLE";
    #   例: List<String> codes = new ArrayList<>();
    #   \b\w[\w<>\[\]]* = 識別子または型名（ジェネリクス・配列も含む）
    (re.compile(r'\b\w[\w<>\[\]]*\s+\w+\s*='),                 "変数代入"),

    # 優先度6: メソッド引数 ("メソッド名(" の形)
    #   例: log.info("SAMPLE");
    #   例: process(code);
    (re.compile(r'\w+\s*\('),                                    "メソッド引数"),

    # 優先度7（暗黙）: 全パターン不一致 → "その他"（コード内には書かれていないが
    # classify_usage_regex() の末尾で UsageType.OTHER を返す）
]

# "Binary file xxx matches" のような grep のバイナリ通知行を検出するパターン。
# grep がバイナリファイルにマッチを見つけた際に出力する特殊行。
# この行はコード行ではないためスキップする。
_BINARY_PATTERN = re.compile(r'^Binary file .+ matches$')

# grep 出力の1行から "filepath:lineno:code" の3要素を取り出すためのパターン。
#
# 【なぜ単純な split(":") を使わないのか】
#   Windowsのファイルパスは "C:\path\file.java:10:code" の形式で、
#   先頭に "C:" というドライブレターが含まれる。
#   split(":", 2) で分割すると ["C", "\\path\\file.java", "10:code"] となり、
#   ファイルパスが壊れてしまう。
#
#   ":10:" のように「コロン + 数字列 + コロン」というパターンだけで分割することで
#   ドライブレターの "C:" を誤って区切り文字と見なさなくて済む。
#   maxsplit=1 で最初の1箇所だけ分割するため、コード行内の ":" も安全。
_GREP_LINE_PATTERN = re.compile(r':(\d+):')

# フィールド宣言を正規表現で判定するパターン（AST が使えない場合のフォールバック用）。
#
# 【マッチ対象の例】
#   private String type = "SAMPLE";
#   protected static int count = 0;
#   public final boolean flag;
#
# 【マッチしない（ローカル変数と判定される）例】
#   String type = "SAMPLE";  ← 修飾子なし（パッケージプライベートフィールド）
#   → AST なら FieldDeclaration ノードで正しく判定できるが正規表現では取りこぼす
_FIELD_DECL_PATTERN = re.compile(
    r'^(private|protected|public|static|final|\s)*\s+\w[\w<>\[\]]*\s+\w+\s*[=;]'
)

# TSV ファイルのヘッダー行（列名の定義）。
# write_tsv() で1行目として書き出す。
_TSV_HEADERS = [
    "文言",         # 検索した文言（grepファイル名から取得）
    "参照種別",     # 直接 / 間接 / 間接（getter経由）
    "使用タイプ",   # 定数定義 / 条件判定 / return文 / 変数代入 / メソッド引数 / アノテーション / その他
    "ファイルパス", # 該当行のJavaファイルパス
    "行番号",       # 該当行の行番号
    "コード行",     # 該当行のコード（前後の空白はtrim済み）
    "参照元変数名", # 間接参照の場合のみ: 経由した変数/定数名
    "参照元ファイル",  # 間接参照の場合のみ: 変数/定数が定義されたファイル
    "参照元行番号",    # 間接参照の場合のみ: 変数/定数が定義された行番号
]


# ============================================================================
# Enum（列挙型）定義
# ============================================================================
#
# 【なぜ文字列定数ではなく Enum を使うのか】
#   Enum を使うと「有効な値の集合」が明示でき、
#   タイポ（"直接参照" と "直接" の書き間違い等）をコード補完で防げる。
#   .value で文字列を取り出せるため、TSV への書き出し時はそのまま使える。
# ============================================================================

class RefType(Enum):
    """参照種別を表す列挙型。

    直接参照   : grep ファイルに書かれた行そのもの
    間接参照   : 変数/定数を経由して実質的に文言を参照している行
    getter 経由: フィールドの getter メソッド呼び出しを経由している行
    """
    DIRECT   = "直接"
    INDIRECT = "間接"
    GETTER   = "間接（getter経由）"


class UsageType(Enum):
    """使用タイプを表す列挙型（7種）。

    コード行が「何をしているか」を表す分類。
    """
    ANNOTATION = "アノテーション"  # @Xxx(...) の形でアノテーション引数として使われている
    CONSTANT   = "定数定義"        # public static final String FOO = "..."; の形
    VARIABLE   = "変数代入"        # ローカル変数またはフィールドへの代入
    CONDITION  = "条件判定"        # if / while / .equals / != / == 等の比較に使われている
    RETURN     = "return文"        # return 文で返されている
    ARGUMENT   = "メソッド引数"    # メソッド呼び出しの引数として渡されている
    OTHER      = "その他"          # 上記のどれにも該当しない（コメントのみの行など）


# ============================================================================
# データモデル
# ============================================================================

@dataclass(frozen=True)
class GrepRecord:
    """分析結果の1件を表すイミュータブル（不変）なデータモデル。

    【frozen=True の意味】
        一度生成したら変更できない（Java の record クラスや immutable クラスに相当）。
        frozen=True にすることで:
          1. 生成後にフィールドを書き換えようとすると例外が発生 → 意図しない変更を防ぐ
          2. __hash__ が自動生成される → set や dict のキーとして使える

    【src_var / src_file / src_lineno の使い方】
        直接参照の場合は空文字列のまま。
        間接参照・getter経由参照の場合に、「経由した変数の情報」を記録するために使う。

        例（SAMPLE_CODE という定数を経由した間接参照）:
          src_var    = "SAMPLE_CODE"         ← 経由した変数名
          src_file   = "Constants.java"      ← SAMPLE_CODE が定義されたファイル
          src_lineno = "9"                   ← SAMPLE_CODE が定義された行番号
    """
    keyword:    str       # 検索した文言（例: "SAMPLE"）。入力ファイル名 SAMPLE.grep から取得。
    ref_type:   str       # 参照種別。RefType.DIRECT.value / RefType.INDIRECT.value 等。
    usage_type: str       # 使用タイプ。UsageType.CONSTANT.value 等の文字列。
    filepath:   str       # 該当行のファイルパス（grep ファイルに書かれていた値をそのまま使用）
    lineno:     str       # 該当行の行番号（文字列のまま保持。数値ソートが必要な箇所で int() 変換）
    code:       str       # 該当行のコード（前後の空白はtrim済み）

    # 以下3フィールドはデフォルト値 "" を持つ（省略可能）。
    # Python の dataclass はデフォルト値を持つフィールドを後ろに置く必要がある。
    src_var:    str = ""  # 間接参照の場合のみ: 経由した変数/定数名
    src_file:   str = ""  # 間接参照の場合のみ: 変数/定数が定義されたファイルパス
    src_lineno: str = ""  # 間接参照の場合のみ: 変数/定数が定義された行番号

    # 【なぜ lineno を int ではなく str で保持するか】
    #   grep ファイルから読んだ値は文字列。TSV 書き出し時も文字列のまま使う。
    #   整数演算が必要な局所的な箇所（_get_method_scope の lineno 比較等）だけ
    #   int(record.lineno) とキャストするほうがシンプル。


@dataclass
class ProcessStats:
    """全 grep ファイルを処理した際の統計情報を格納するデータクラス。

    main() ループ全体で1つのインスタンスを使い回し、
    各関数が stats.xxx += 1 や stats.fallback_files.append() で更新する。
    最終的に print_report() でサマリとして表示される。
    """
    total_lines:     int = 0    # grep ファイル全行数（空行やバイナリ通知行も含む）
    valid_lines:     int = 0    # GrepRecord が生成された行数（有効な grep 結果行）
    skipped_lines:   int = 0    # 空行・バイナリ通知・形式不正などでスキップした行数

    # 【なぜリストのデフォルト値に = [] と書けないのか】
    #   Python のデフォルト引数／フィールドは「定義時に1回だけ評価」される。
    #   = [] と書くと「全インスタンスが同一のリストオブジェクトを共有」してしまい、
    #   stats1 にファイルを追加すると stats2 にも混入するバグが発生する。
    #   field(default_factory=list) を使うと「インスタンス生成のたびに list() を呼ぶ」
    #   つまり「毎回新しいリストを作る」ことが保証される。
    fallback_files:  list[str] = field(default_factory=list)
    # AST パースに失敗し、正規表現で代替したファイルのパスリスト。
    # javalang はインストールされているが、特定ファイルの構文が javalang 非対応の場合に記録。

    encoding_errors: list[str] = field(default_factory=list)
    # ファイル読み込み時にエンコーディング例外が発生したファイルのパスリスト。


# ============================================================================
# AST キャッシュ（モジュールレベル変数・プロセス内シングルトン）
# ============================================================================
#
# キー   : ファイルパス文字列
# 値     : javalang の CompilationUnit オブジェクト（パース成功時）
#          または None（パースエラー / ファイル不在）
#
# 【None と「キーが存在しない」の区別について】
#   _ast_cache["Bad.java"] = None  → 「以前試みたがパースに失敗した」ことを意味する
#   "New.java" not in _ast_cache   → 「まだ試みていない」ことを意味する
#   → dict.get() は両方とも None を返すため区別できない。
#   → 「キーの存在確認」には in 演算子（Java の Map.containsKey() 相当）を使う。
_ast_cache: dict[str, object | None] = {}


# ============================================================================
# F-01: GrepParser
# ─── grep ファイルを読み込み、直接参照の GrepRecord リストを生成する ─────────
# ============================================================================

def parse_grep_line(line: str) -> dict | None:
    """grep 結果の1行をパースし、辞書を返す。不正行は None を返す。

    grep の出力形式:
        filepath:lineno:code
        例: "tests/fixtures/java/Constants.java:9:    public static final String SAMPLE_CODE = \"SAMPLE\";"

    Windows パス対応:
        "C:\\path\\file.java:10:code" のようなドライブレターを含む場合でも正しく分割できる。
        → re.split(r':(\\d+):', line, maxsplit=1) を使用（単純な split(":") では C: で誤分割）

    Args:
        line: grep 結果の1行（ファイルから読んだ生の行）

    Returns:
        {'filepath': str, 'lineno': str, 'code': str} の辞書
        または不正行の場合 None
    """
    # 末尾の改行文字（\n, \r\n, \r）を除去する。
    # 【なぜ strip() ではなく rstrip('\n\r') を使うのか】
    #   strip() は前後の空白文字をすべて除去してしまう。
    #   filepath の先頭に空白が含まれる場合（稀だが）に情報を失う可能性があるため、
    #   末尾の改行のみを除去する rstrip('\n\r') を使う。
    stripped = line.rstrip('\n\r')

    # 空行はスキップ（grep ファイルにはセクション区切りとして空行が含まれることがある）
    if not stripped.strip():
        return None

    # "Binary file tests/fixtures/binary.class matches" のようなバイナリ通知行をスキップ。
    # grep がバイナリファイルにマッチを見つけた際に出力する特殊メッセージ。
    if _BINARY_PATTERN.match(stripped):
        return None

    # ":数字:" のパターンで分割する（maxsplit=1 で最初の1箇所だけ分割）。
    #
    # re.split(r':(\\d+):', ...) はキャプチャグループ (\d+) を持つため、
    # 分割された結果リストに「マッチした数字（行番号）」も含まれる。
    # 例: "Foo.java:9:code" → ["Foo.java", "9", "code"]
    #
    # maxsplit=1 の理由:
    #   コード行の中に ":" が含まれる場合（"a:b"、三項演算子 "x ? a : b" 等）に
    #   そこを区切り文字と誤認しないようにするため。
    parts = _GREP_LINE_PATTERN.split(stripped, maxsplit=1)

    # 正しく分割できた場合は ["filepath", "lineno", "code"] の3要素になる。
    # 3要素にならない場合はフォーマット不正として None を返す。
    if len(parts) != 3:
        return None

    # Python のアンパック代入: a, b, c = リスト（Java の分割代入には相当構文なし）
    filepath, lineno, code = parts

    # filepath または lineno が空文字の場合もスキップ
    if not filepath or not lineno:
        return None

    return {
        "filepath": filepath,
        "lineno":   lineno,
        "code":     code.strip(),  # コード行の前後の空白（インデント等）を除去
    }


def process_grep_file(
    path: Path,
    keyword: str,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """grep ファイル全行を処理し、直接参照の GrepRecord リストを返す。

    各行を parse_grep_line() でパースし、
    classify_usage() で使用タイプを判定してから GrepRecord を生成する。
    生成したレコードはすべて ref_type="直接" になる。

    Args:
        path:       処理する .grep ファイルのパス
        keyword:    検索文言（grepファイル名の拡張子なし部分。例: "SAMPLE"）
        source_dir: Java ソースコードのルートディレクトリ（AST 解析に使用）
        stats:      処理統計（この関数内で更新される）

    Returns:
        直接参照 GrepRecord のリスト（使用タイプ付き）
    """
    # ファイルサイズチェック（500MB 超の場合は警告を出して処理は続行）
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > 500:
        print(
            f"警告: {path.name} のサイズが {file_size_mb:.1f}MB を超えています。処理に時間がかかる場合があります。",
            file=sys.stderr,
        )

    records: list[GrepRecord] = []

    # with ブロック = Java の try-with-resources に相当。
    # ブロックを抜けると（例外が発生しても）自動でファイルが閉じられる。
    # errors="replace" で読めない文字を置換文字（）に変換して処理を続行する。
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            # ファイルオブジェクトをそのままイテレートすると1行ずつ読む（メモリ効率が良い）
            stats.total_lines += 1  # 全行数をカウント（空行・バイナリ通知行も含む）

            parsed = parse_grep_line(line)
            if parsed is None:
                # 空行・バイナリ通知行・形式不正行はスキップ
                stats.skipped_lines += 1
                continue

            # コード行の使用タイプを分類する（AST 優先 → 正規表現フォールバック）
            usage_type = classify_usage(
                code=parsed["code"],
                filepath=parsed["filepath"],
                lineno=int(parsed["lineno"]),  # AST の position.line と比較するため int に変換
                source_dir=source_dir,
                stats=stats,
            )

            # 直接参照レコードを生成。src_var / src_file / src_lineno は空のまま（直接参照のため）。
            records.append(GrepRecord(
                keyword=keyword,
                ref_type=RefType.DIRECT.value,   # "直接" という文字列
                usage_type=usage_type,
                filepath=parsed["filepath"],
                lineno=parsed["lineno"],          # 文字列のまま保持
                code=parsed["code"],
            ))
            stats.valid_lines += 1  # 有効行数をカウント

    return records


# ============================================================================
# F-02: UsageClassifier
# ─── コード行の使用タイプを判定する（AST 優先・正規表現フォールバック） ───────
# ============================================================================

def get_ast(filepath: str, source_dir: Path) -> object | None:
    """Java ファイルを解析して AST（抽象構文木）を返す。キャッシュを利用して再解析を省略する。

    【AST とは】
        Abstract Syntax Tree（抽象構文木）。
        Java ソースコードのテキストをパースして得られる木構造データ。
        各ノードが「クラス定義」「メソッド定義」「if 文」「return 文」等の構文要素を表す。
        これを使うと "private String type = ..." が
        「フィールド宣言」か「ローカル変数宣言」かを正確に区別できる。

    【キャッシュの仕組み】
        同じファイルを複数行処理する際（10行 hit したファイル等）に毎回パースするのは無駄。
        モジュールレベルの _ast_cache 辞書に結果を保存し、2回目以降はキャッシュを返す。
        パースに失敗したファイルも None としてキャッシュし、再試行しない。

    Args:
        filepath:   Java ファイルのパス（相対パスまたは絶対パス）
        source_dir: Java ソースのルートディレクトリ（相対パス解決に使用）

    Returns:
        javalang の CompilationUnit（パース成功時）
        または None（javalang 未インストール / ファイル不在 / 構文エラー）
    """
    # javalang がインストールされていない場合は即 None を返す
    if not _JAVALANG_AVAILABLE:
        return None

    # キャッシュキーはファイルパスの文字列表現
    cache_key = str(filepath)

    # 【なぜ get() でなく in を使うのか】
    #   _ast_cache["Bad.java"] = None（パース失敗のキャッシュ）と
    #   "New.java" が未登録の場合を区別するため。
    #   dict.get() は両方とも None を返してしまう。
    if cache_key in _ast_cache:
        # キャッシュにあればそのまま返す（None の場合も「パース失敗確認済み」として返す）
        return _ast_cache[cache_key]

    # ファイルパスを解決する（相対パスの場合は source_dir を基底にする）
    candidate = Path(filepath)
    if not candidate.is_absolute():
        # 相対パスは source_dir からの相対として解釈する
        candidate = source_dir / filepath

    # ファイルが存在しない場合は None としてキャッシュして返す
    if not candidate.exists():
        _ast_cache[cache_key] = None
        return None

    try:
        # Java ファイルを読み込む。
        # 【なぜ Shift-JIS で読むのか】
        #   古い Java プロジェクトのソースファイルはコメントや文字列リテラルに
        #   Shift-JIS が使われていることが多い。
        #   errors="replace" と組み合わせることで、読めない文字があっても処理を継続できる。
        #   AST 解析が目的のため、コメント内の文字が化けても構文構造には影響しない。
        source = candidate.read_text(encoding="shift_jis", errors="replace")

        # javalang.parse.parse() に Java ソースコード全文を渡すと
        # CompilationUnit（ファイル全体を表すルートノード）が返ってくる。
        tree = javalang.parse.parse(source)
        _ast_cache[cache_key] = tree  # パース成功をキャッシュ

    except Exception:
        # javalang.parser.JavaSyntaxError や IOError を含む全例外をキャッチし、
        # None としてキャッシュする（次回から再試行しない）。
        _ast_cache[cache_key] = None

    return _ast_cache[cache_key]


def classify_usage_regex(code: str) -> str:
    """正規表現でコード行の使用タイプを分類する（フォールバック専用）。

    USAGE_PATTERNS を先頭から順番に評価し、最初にマッチしたラベルを返す。
    全パターン不一致の場合は "その他" を返す。

    【なぜ「フォールバック専用」か】
        正規表現はコード行の文字列パターンしか見られないため、
        AST 判定より精度が低い。特に:
        - パッケージプライベートフィールド（修飾子なし）を取りこぼす
        - コメントアウトされた行を誤判定する可能性がある
        AST が使える場合は get_ast() + _classify_by_ast() を使い、
        AST が使えない場合のみこの関数が呼ばれる。

    Args:
        code: 分類対象のコード行（前後の空白はtrim済みを推奨）

    Returns:
        UsageType の value 文字列（7種のいずれか）
    """
    stripped = code.strip()
    for pattern, usage_type in USAGE_PATTERNS:
        # pattern.search() は行全体のどこかにマッチすれば True を返す
        # （pattern.match() は先頭からのマッチのみ）
        if pattern.search(stripped):
            return usage_type
    # 全パターン不一致 = コメントのみの行や認識できない構文
    return UsageType.OTHER.value


def classify_usage(
    code: str,
    filepath: str,
    lineno: int,
    source_dir: Path,
    stats: ProcessStats,
) -> str:
    """コード行の使用タイプを判定して文字列を返す。

    判定の優先順位:
      1. AST（構文木）による精密判定  ← javalang が使える場合
      2. 正規表現によるフォールバック ← AST が使えない場合

    Args:
        code:       分類対象のコード行（前後の空白はtrim済み）
        filepath:   Java ファイルのパス（AST 解析に使用）
        lineno:     対象行の行番号（AST のノード位置情報との照合に使用）
        source_dir: Java ソースのルートディレクトリ
        stats:      処理統計（フォールバック件数の記録に使用）

    Returns:
        UsageType の value 文字列（7種のいずれか）
    """
    # まず AST を取得する（キャッシュがあれば即返る・なければパース）
    tree = get_ast(filepath, source_dir)

    if tree is None:
        # AST が取得できなかった場合は正規表現フォールバックへ。
        # javalang はインストールされているのにパース失敗した場合のみ fallback_files に記録する。
        # （javalang が未インストールの場合は「仕様上の動作」なので記録しない）
        if _JAVALANG_AVAILABLE and filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)
        return classify_usage_regex(code)

    # AST が取得できた場合は行番号でノードを特定して使用タイプを判定する
    try:
        usage = _classify_by_ast(tree, lineno)
        if usage is not None:
            # AST で判定できた場合はその結果を返す
            return usage
        # usage == None = AST を走査したが対象行のノードが見つからなかった
        # → フォールバックへ（後続の return で処理）
    except Exception:
        # AST 走査中の予期しない例外（javalang の内部エラー等）
        # フォールバック対象として記録してから正規表現へ
        if filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)

    # AST で判定できなかった場合（ノード不在 / 例外）は正規表現フォールバック
    return classify_usage_regex(code)


def _classify_by_ast(tree: object, lineno: int) -> str | None:
    """AST ノードの行番号から使用タイプを判定する（内部ヘルパー）。

    【動作の仕組み】
        javalang の CompilationUnit は「全ノードを深さ優先でイテレートできる」イテラブル。
        `for _, node in tree:` と書くと全ノードを順番に取り出せる。
        各ノードは position.line（何行目に書かれているか）を持つ。
        → 対象行番号 (lineno) に一致するノードを探し、そのノード型で使用タイプを判定する。

    【走査の例（Constants.java の行9を探す場合）】
        node1: CompilationUnit      → position=None → スキップ
        node2: ClassDeclaration     → position.line=6 ≠ 9 → スキップ
        node3: FieldDeclaration     → position.line=9 == 9 → ヒット！
          modifiers = {"public", "static", "final"}
          "static" in modifiers AND "final" in modifiers → True
          → return "定数定義"（ここで即座に return。残りは走査しない）

    Args:
        tree:   javalang の CompilationUnit（get_ast() の戻り値）
        lineno: 対象行の行番号

    Returns:
        UsageType の value 文字列、または対象行のノードが見つからない場合は None
    """
    if not _JAVALANG_AVAILABLE:
        return None

    # tree をイテレートすると (path情報, node) のタプルが深さ優先で yield される。
    # path 情報は今回使わないため _ で受け取って捨てる。
    for _, node in tree:
        # position 属性がない、または position が None のノードは行番号を持たないのでスキップ。
        # （CompilationUnit 自体、型パラメータ、import 宣言など）
        if not hasattr(node, 'position') or node.position is None:
            continue

        # 対象行番号と一致しないノードはスキップ
        if node.position.line != lineno:
            continue

        # ─── 対象行のノードが見つかった ─────────────────────────────────────────
        # isinstance() で Java の instanceof に相当するノード型チェックを行う。

        # ① アノテーション: @Xxx(...) の形
        if isinstance(node, javalang.tree.Annotation):
            return UsageType.ANNOTATION.value

        # ② フィールド宣言またはローカル変数宣言
        #    (定数定義 / 変数代入 の2種類に細分化する)
        if isinstance(node, (
            javalang.tree.FieldDeclaration,           # クラスのフィールド（インスタンス変数・静的変数）
            javalang.tree.LocalVariableDeclaration,   # メソッド内のローカル変数
        )):
            # modifiers（修飾子セット）を安全に取得する。
            # 【なぜ二重ガードするのか】
            #   getattr(node, 'modifiers', set()) だけでは、
            #   属性は存在するが値が None の場合に None が返り、
            #   'static' in None で TypeError が発生してしまう。
            #   → or set() で「None が返ってきた場合も空セットにする」という二段構え。
            modifiers = getattr(node, 'modifiers', set()) or set()
            if 'static' in modifiers and 'final' in modifiers:
                # static かつ final = 定数定義（Java の public static final String CODE = ...）
                return UsageType.CONSTANT.value
            # static/final でなければ通常の変数代入（フィールドまたはローカル変数）
            return UsageType.VARIABLE.value

        # ③ if 文 / while 文（条件判定）
        if isinstance(node, (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
        )):
            return UsageType.CONDITION.value

        # ④ return 文
        if isinstance(node, javalang.tree.ReturnStatement):
            return UsageType.RETURN.value

        # ⑤ メソッド呼び出し / コンストラクタ呼び出し（メソッド引数）
        #    MethodInvocation: foo.bar(arg)、log.info(msg) 等
        #    ClassCreator:     new Foo(arg) 等
        if isinstance(node, (
            javalang.tree.MethodInvocation,
            javalang.tree.ClassCreator,
        )):
            return UsageType.ARGUMENT.value

        # 上記のどのノード型にも該当しない場合（MemberReference、Literal 等）は
        # このノードではなく次のノードで判定を試みる（ループ継続）

    # 対象行番号のノードが1つも見つからなかった場合は None を返す（フォールバックへ）
    return None


# ============================================================================
# F-03: IndirectTracker
# ─── 変数・定数・フィールドの使用箇所を追跡して間接参照レコードを生成する ───
# ============================================================================

def determine_scope(
    usage_type: str,
    code: str,
    filepath: str = "",
    source_dir: Path | None = None,
    lineno: int = 0,
) -> str:
    """変数の種類（スコープ）に応じた追跡範囲を返す。

    スコープ種別と意味:
        "project" : プロジェクト全体（全 .java ファイル）を追跡対象にする
                    → static final 定数は他クラスから参照できるため
        "class"   : 同一クラスファイル内のみを追跡対象にする
                    → フィールドは自クラスのメソッドからしか通常参照されないため
        "method"  : 同一メソッドの行範囲内のみを追跡対象にする
                    → ローカル変数はメソッドの外から参照できないため

    【AST による正確な判定と正規表現フォールバックの使い分け】
        正規表現の _FIELD_DECL_PATTERN は修飾子（private/public 等）が必要なため、
        パッケージプライベートフィールド（修飾子なし: String type = "SAMPLE";）を
        ローカル変数として誤判定してしまう。
        AST を使えば FieldDeclaration ノードか LocalVariableDeclaration ノードかを
        直接確認できるため、修飾子の有無にかかわらず正確に判定できる。

    Args:
        usage_type:  UsageType の value 文字列
        code:        変数定義のコード行
        filepath:    Java ファイルのパス（AST 判定に使用。省略時は正規表現フォールバック）
        source_dir:  Java ソースのルートディレクトリ（AST 判定に使用）
        lineno:      対象行の行番号（AST 判定に使用）

    Returns:
        "project" / "class" / "method" のいずれか
    """
    # static final 定数（UsageType.CONSTANT）は必ず "project" スコープ
    if usage_type == UsageType.CONSTANT.value:
        return "project"

    # AST が使える条件がすべて揃っている場合は AST で正確に判定する
    if filepath and source_dir and lineno and _JAVALANG_AVAILABLE:
        tree = get_ast(filepath, source_dir)
        if tree is not None:
            try:
                for _, node in tree:
                    if not hasattr(node, 'position') or node.position is None:
                        continue
                    if node.position.line != lineno:
                        continue
                    # FieldDeclaration = クラスのフィールド → "class" スコープ
                    if isinstance(node, javalang.tree.FieldDeclaration):
                        return "class"
                    # LocalVariableDeclaration = メソッド内のローカル変数 → "method" スコープ
                    if isinstance(node, javalang.tree.LocalVariableDeclaration):
                        return "method"
            except Exception:
                # AST 走査エラーは無視して正規表現フォールバックへ
                pass

    # AST が使えない場合（または対象ノードが見つからなかった場合）は正規表現で判定
    stripped = code.strip()
    if _FIELD_DECL_PATTERN.match(stripped):
        # _FIELD_DECL_PATTERN にマッチ = private/public 等の修飾子がある → フィールド
        return "class"
    # 上記に該当しない場合はローカル変数と見なす
    return "method"


def extract_variable_name(code: str, usage_type: str) -> str | None:  # noqa: ARG001
    """定数/変数の名前をコード行から抽出して返す。

    「= の左辺の最後のトークン」を変数名として取り出す。

    【動作の例】
        "public static final String SAMPLE_CODE = \"SAMPLE\";"
          → rstrip(';') → split('=')[0] → "public static final String SAMPLE_CODE"
          → split()     → ["public","static","final","String","SAMPLE_CODE"]
          → tokens[-1]  → "SAMPLE_CODE"  ← 変数名

        "private String type = \"SAMPLE\";"
          → ... → "type"

        "private String type;"  (初期値なしの宣言)
          → rstrip(';') → split('=')[0] → "private String type"
          → tokens[-1]  → "type"

        "if (x.equals(\"SAMPLE\")) {"  (変数宣言でない行)
          → ... → "{"
          → isidentifier("{") → False
          → None（変数名を抽出できなかった）

    Args:
        code:       変数定義のコード行
        usage_type: 使用タイプ文字列（現在は使用しないが将来拡張のためのインターフェース）

    Returns:
        変数名の文字列、または抽出できない場合は None
    """
    # まず末尾のセミコロンを除去する（rstrip はリストの文字のどれかを除去する関数）。
    # 【なぜ rstrip(';') で strip(';') でないのか】
    #   セミコロンは行末にしか来ないため rstrip（末尾のみ除去）で十分。
    #   strip(';') だと先頭のセミコロンも除去してしまい（実際にはないが）意図が不明確になる。
    stripped = code.strip().rstrip(';')

    # "=" で分割して左辺だけ取り出す（split('=') は全ての = で分割するが [0] で最初だけ使う）
    # 例: 'public static final String CODE = "SAMPLE"' → 'public static final String CODE '
    decl_part = stripped.split('=')[0].strip()

    # 空白で分割してトークン列を得る
    tokens = decl_part.split()

    # トークンが2つ以上あれば「最後のトークン」が変数名
    # （例: ["public","String","CODE"] の場合、最後の "CODE" が変数名）
    # トークンが1つ以下の場合は変数宣言の形式になっていないのでスキップ
    if len(tokens) >= 2:
        # tokens[-1] = リストの最後の要素（Python の負インデックス）
        # strip('[];(){}<>') で括弧類が付いている場合に除去
        name = tokens[-1].strip('[];(){}<>')
        # isidentifier() で "CODE"、"type" 等の識別子かどうかを確認
        # （"{"、")" 等の記号は False を返す）
        if name.isidentifier():
            return name
    return None


def _resolve_java_file(filepath: str, source_dir: Path) -> Path | None:
    """ファイルパス文字列を実在する Path オブジェクトに解決する（内部ヘルパー）。

    絶対パスと相対パスの両方に対応する。
    相対パスの場合は source_dir からの相対として解釈する。

    Args:
        filepath:   Java ファイルのパス（相対または絶対）
        source_dir: Java ソースのルートディレクトリ

    Returns:
        実在する Path オブジェクト、または解決できない場合は None
    """
    candidate = Path(filepath)
    if candidate.is_absolute():
        # 絶対パスの場合はそのままファイルの存在確認
        return candidate if candidate.exists() else None
    # 相対パスの場合は source_dir を基底にして解決する
    resolved = source_dir / filepath
    if resolved.exists():
        return resolved
    return None


def _get_method_scope(
    filepath: str, source_dir: Path, lineno: int
) -> tuple[int, int] | None:
    """指定行を含むメソッドの行範囲 (start_line, end_line) を返す（内部ヘルパー）。

    【なぜ行範囲の特定が必要か】
        ローカル変数はメソッド外からは参照できない。
        そのため、ローカル変数の使用箇所追跡は「同一メソッドの行範囲内だけ」に限定する。
        この関数が「そのメソッドは何行目から何行目か」を特定する。

    【2段階で行範囲を求める】
        ① javalang の AST から MethodDeclaration ノードを全収集し、開始行番号のリストを作る
        ② ブレースカウンタ（{} の入れ子を数える）で終了行を特定する

        javalang の AST ノードは「開始行（position.line）」しか持たず「終了行」は持たない。
        そのためブレースカウンタでテキストを走査して終了行を自力で求める必要がある。

    【ブレースカウンタの仕組み】
        メソッド開始行から走査を開始し、'{' が来るたびに +1、'}' が来るたびに -1。
        最初の '{' を見た後（found_open=True）に カウンタが 0 以下になった行がメソッド終了行。

        例:
          i=12: "... {" → count=1, found_open=True
          i=13: "  if (...) {" → count=2
          i=14: "    return true;" → count=2
          i=15: "  }" → count=1
          i=16: "  return false;" → count=1
          i=17: "}" → count=0, found_open=True かつ count≤0 → return (12, 17)

    Args:
        filepath:   Java ファイルのパス
        source_dir: Java ソースのルートディレクトリ
        lineno:     ローカル変数が定義された行番号

    Returns:
        (start_line, end_line) のタプル（1-indexed）
        または特定不能な場合は None
    """
    # javalang が使えない場合はメソッド行範囲を特定できない（None を返す）
    if not _JAVALANG_AVAILABLE:
        return None

    # AST を取得（キャッシュから返ることが多い）
    tree = get_ast(filepath, source_dir)
    if tree is None:
        return None

    # ① AST から全メソッドの開始行番号を収集する
    method_starts: list[int] = []
    try:
        # tree.filter(NodeType) は特定のノード型だけをフィルタリングするイテレータを返す
        for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
            if method_decl.position:
                method_starts.append(method_decl.position.line)
    except Exception:
        return None

    if not method_starts:
        return None

    method_starts.sort()  # 昇順ソート（後でバイナリサーチ的に使う）

    # lineno を含むメソッドの開始行を特定する。
    # 「lineno 以下で最大の開始行」が lineno を含むメソッドの開始行になる。
    # 例: method_starts=[5, 12, 20], lineno=15 の場合
    #   start=5  ≤ 15 → method_start=5
    #   start=12 ≤ 15 → method_start=12  （上書き）
    #   start=20 > 15 → スキップ
    #   → method_start=12 が答え（12行目から始まるメソッドに lineno=15 が含まれる）
    method_start = None
    for start in method_starts:
        if start <= lineno:
            method_start = start  # 条件を満たす最大値を都度上書き

    if method_start is None:
        # lineno が全メソッドの開始行より前にある場合（異常ケース）
        return None

    # ② ブレースカウンタでメソッドの終了行を特定する
    java_file = _resolve_java_file(filepath, source_dir)
    if java_file is None:
        return None

    try:
        lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
        # splitlines() で改行文字を含まない行のリスト（0-indexed）に変換
    except Exception:
        return None

    brace_count = 0   # '{' と '}' の差分（入れ子の深さを表す）
    found_open = False  # 最初の '{' を見たかどうかのフラグ

    # enumerate(lines[method_start - 1:], start=method_start):
    #   lines[method_start - 1:] = メソッド開始行から末尾までのスライス（0-indexed）
    #   start=method_start で「インデックスが 1-indexed の行番号」になるよう指定
    for i, line in enumerate(lines[method_start - 1:], start=method_start):
        # この行に含まれる '{' の数 - '}' の数をカウンタに加算
        brace_count += line.count('{') - line.count('}')

        # 最初の '{' を見たら found_open フラグを立てる
        # 【found_open が必要な理由】
        #   メソッドシグネチャ "public void foo()" のような行には '{' がない。
        #   found_open なしだと、'{' を見る前に他の要因でカウンタが 0 以下になった場合に
        #   誤ってそこを終了行と判断してしまう。
        if not found_open and brace_count > 0:
            found_open = True

        # found_open=True かつ カウンタ≤0 になったところがメソッドの終了行
        if found_open and brace_count <= 0:
            return (method_start, i)

    # ファイル末尾まで走査しても終了行が見つからなかった（異常ケース）
    return None


def _search_in_lines(
    lines: list[str],
    var_name: str,
    start_line: int,
    origin: GrepRecord,
    source_dir: Path,
    ref_type: str,
    stats: ProcessStats,
    filepath_for_record: str,
) -> list[GrepRecord]:
    """行リストから変数名を検索し、ヒットした行の GrepRecord を生成して返す（内部ヘルパー）。

    track_constant() / track_field() / track_local() が共通して呼び出す汎用検索関数。

    【検索パターン】
        r'\b変数名\b' という単語境界マッチを使用する。
        \b がないと "errorCode" を検索したときに "code" でもヒットしてしまう。
        \b があることで「単語として独立して存在する」場合のみマッチする。

    【定義行のスキップ】
        変数の定義行（origin.filepath + origin.lineno）は間接参照として出力しない。
        「SAMPLE_CODE = "SAMPLE" の定義行が SAMPLE_CODE の使用箇所として2重出力される」
        ことを防ぐため。

    Args:
        lines:               検索対象の行リスト（0-indexed のリスト）
        var_name:            検索する変数名（\b で単語境界マッチ）
        start_line:          lines[0] に対応する行番号（1-indexed）
        origin:              間接参照元の直接参照レコード（定義行の情報）
        source_dir:          Java ソースのルートディレクトリ（使用タイプ判定に使用）
        ref_type:            生成する GrepRecord の参照種別（"間接" または "間接（getter経由）"）
        stats:               処理統計
        filepath_for_record: 生成する GrepRecord に記録するファイルパス文字列

    Returns:
        生成した GrepRecord のリスト
    """
    # re.escape(var_name) で変数名の特殊文字をエスケープする（Java の Pattern.quote() 相当）
    # \b ... \b で単語境界マッチを設定する
    pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
    records: list[GrepRecord] = []

    # enumerate(lines) は (インデックス, 行文字列) のタプルを返す
    # idx は 0-indexed、current_lineno は 1-indexed の行番号
    for idx, line in enumerate(lines):
        current_lineno = start_line + idx  # 1-indexed の行番号に変換

        # 変数の定義行はスキップ（同一ファイル・同一行番号の場合）
        # str(current_lineno) と origin.lineno（文字列）を比較する
        if (filepath_for_record == origin.filepath
                and str(current_lineno) == origin.lineno):
            continue

        # 変数名のパターンにマッチしない行はスキップ
        if not pattern.search(line):
            continue

        # ヒットした行の使用タイプを分類する（AST 優先）
        code = line.strip()
        usage_type = classify_usage(
            code=code,
            filepath=filepath_for_record,
            lineno=current_lineno,
            source_dir=source_dir,
            stats=stats,
        )

        # 間接参照レコードを生成。src_var / src_file / src_lineno に変数定義元の情報を記録する。
        records.append(GrepRecord(
            keyword=origin.keyword,
            ref_type=ref_type,                 # "間接" または "間接（getter経由）"
            usage_type=usage_type,
            filepath=filepath_for_record,
            lineno=str(current_lineno),        # 文字列に変換して保持
            code=code,
            src_var=var_name,                  # 経由した変数名（追跡のきっかけ）
            src_file=origin.filepath,          # 変数が定義されていたファイル
            src_lineno=origin.lineno,          # 変数が定義されていた行番号
        ))

    return records


def track_constant(
    var_name: str,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """static final 定数をプロジェクト全体（全 .java ファイル）で追跡する。

    【なぜプロジェクト全体を検索するのか】
        static final 定数は他クラスからも "Constants.CODE" のように参照できる。
        そのためソースディレクトリ以下の全 .java ファイルが検索対象になる。

    Args:
        var_name:   追跡する定数名（例: "SAMPLE_CODE"）
        source_dir: Java ソースのルートディレクトリ
        origin:     定数定義の直接参照レコード（定義行の情報として src_* に埋め込む）
        stats:      処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    records: list[GrepRecord] = []

    # source_dir.rglob("*.java") でディレクトリ再帰的に全 .java ファイルを列挙する
    # sorted() でアルファベット順に並べることで処理順を安定させる
    for java_file in sorted(source_dir.rglob("*.java")):
        try:
            # Shift-JIS で読み込む（errors="replace" で読めない文字は置換）
            lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
        except Exception:
            # 読み込み失敗したファイルは encoding_errors に記録してスキップ
            stats.encoding_errors.append(str(java_file))
            continue

        # _search_in_lines() で変数名の使用箇所を検索して GrepRecord を収集
        records.extend(_search_in_lines(
            lines=lines,
            var_name=var_name,
            start_line=1,              # ファイル全体なので1行目から
            origin=origin,
            source_dir=source_dir,
            ref_type=RefType.INDIRECT.value,  # "間接"
            stats=stats,
            filepath_for_record=str(java_file),
        ))

    return records


def track_field(
    var_name: str,
    class_file: Path,
    origin: GrepRecord,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """フィールドを同一クラスファイル内で追跡する。

    【なぜクラス内だけを検索するのか】
        フィールド（インスタンス変数）は原則として同一クラスのメソッドからしか
        直接参照されない（getter 経由の参照は track_getter_calls() で別途追跡する）。

    Args:
        var_name:   追跡するフィールド名（例: "type"）
        class_file: フィールドが定義されたJavaファイルの Path
        origin:     フィールド定義の直接参照レコード
        source_dir: Java ソースのルートディレクトリ
        stats:      処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    try:
        lines = class_file.read_text(encoding="shift_jis", errors="replace").splitlines()
    except Exception:
        stats.encoding_errors.append(str(class_file))
        return []

    return _search_in_lines(
        lines=lines,
        var_name=var_name,
        start_line=1,              # クラスファイル全体（1行目から）を検索対象にする
        origin=origin,
        source_dir=source_dir,
        ref_type=RefType.INDIRECT.value,
        stats=stats,
        filepath_for_record=str(class_file),
    )


def track_local(
    var_name: str,
    method_scope: tuple[int, int],
    origin: GrepRecord,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """ローカル変数を同一メソッドの行範囲内で追跡する。

    【なぜメソッド内だけを検索するのか】
        ローカル変数はメソッドの外から参照できない（スコープがメソッド内に限定される）。
        そのためメソッドの行範囲（start_line ～ end_line）だけを検索対象にする。

    Args:
        var_name:     追跡するローカル変数名（例: "msg"）
        method_scope: _get_method_scope() が返した (start_line, end_line) のタプル
        origin:       変数定義の直接参照レコード
        source_dir:   Java ソースのルートディレクトリ
        stats:        処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    java_file = _resolve_java_file(origin.filepath, source_dir)
    if java_file is None:
        return []

    try:
        all_lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
    except Exception:
        stats.encoding_errors.append(str(java_file))
        return []

    start_line, end_line = method_scope

    # 0-indexed スライスでメソッドの行範囲だけを切り出す。
    # all_lines は 0-indexed なので:
    #   start_line=12 → all_lines[11] が12行目
    #   end_line=17   → all_lines[16] が17行目
    #   スライス all_lines[11:17] = インデックス 11, 12, 13, 14, 15, 16 の6行
    method_lines = all_lines[start_line - 1:end_line]

    return _search_in_lines(
        lines=method_lines,
        var_name=var_name,
        start_line=start_line,    # 元ファイルの行番号を正しく計算するために渡す
        origin=origin,
        source_dir=source_dir,
        ref_type=RefType.INDIRECT.value,
        stats=stats,
        filepath_for_record=origin.filepath,
    )


# ============================================================================
# F-04: GetterTracker
# ─── フィールドの getter 呼び出し箇所を追跡して間接（getter経由）レコードを生成する
# ============================================================================

def find_getter_names(field_name: str, class_file: Path) -> list[str]:
    """クラスファイルから getter メソッド名の候補リストを返す。

    【なぜ2方式を組み合わせるのか】
        方式1（命名規則）だけでは "fetchCurrentType()" のような非標準命名を見逃す。
        方式2（AST の return 文解析）では "return type;" しているメソッドを全て拾えるため
        非標準命名にも対応できる。

    【2方式の詳細】

        方式1 — Java Bean 命名規則
          field_name="type" → "get" + "t".upper() + "ype" = "getType"
          先頭1文字を大文字化した後ろに "get" を付ける。

        方式2 — AST の return 文解析
          クラスの全メソッドを走査し、"return field_name;" というパターンの
          return 文を持つメソッドを全て getter 候補とする。
          例: "return type;" → stmt.expression.member == "type" → True

    【false positive（誤検出）の許容について】
        track_getter_calls() はプロジェクト内の同名メソッド呼び出しを全て拾う。
        例えば全く別のクラスが持つ "getType()" も検出される。
        設計方針として「見逃しより誤検出のほうが許容できる（漏れのない一覧を優先）」
        という判断をしているため、これは仕様上の動作。

    Args:
        field_name: フィールド名（例: "type"）
        class_file: フィールドが定義されたJavaファイルの Path

    Returns:
        getter 候補名の重複なしリスト（例: ["getType", "fetchCurrentType"]）
    """
    candidates: list[str] = []

    # 方式1: Java Bean 命名規則で getter 名を構成する
    # field_name[0].upper() = 先頭文字を大文字化
    # field_name[1:]         = 2文字目以降（Python のスライス。Java の substring(1) 相当）
    getter_by_convention = "get" + field_name[0].upper() + field_name[1:]
    candidates.append(getter_by_convention)

    # 方式2: AST で "return field_name;" しているメソッドを探す
    if _JAVALANG_AVAILABLE:
        cache_key = str(class_file)
        # キャッシュに未登録の場合のみパースする
        if cache_key not in _ast_cache:
            try:
                source = class_file.read_text(encoding="shift_jis", errors="replace")
                _ast_cache[cache_key] = javalang.parse.parse(source)
            except Exception:
                _ast_cache[cache_key] = None

        tree = _ast_cache[cache_key]
        if tree is not None:
            try:
                # tree.filter(MethodDeclaration) = MethodDeclaration ノードだけを取り出すイテレータ
                for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
                    # 各メソッド内の return 文をフィルタリング
                    for _, stmt in method_decl.filter(javalang.tree.ReturnStatement):
                        # stmt.expression が MemberReference の場合、.member が変数名になる
                        # 例: "return type;" → stmt.expression = MemberReference(member="type")
                        if (stmt.expression is not None
                                and hasattr(stmt.expression, 'member')
                                and stmt.expression.member == field_name):
                            # このメソッドは "return field_name;" しているので getter 候補
                            candidates.append(method_decl.name)
            except Exception:
                # AST walk 失敗時は方式1（命名規則）のみで継続
                print(
                    f"警告: {class_file} のAST walk中にエラーが発生しました。"
                    "getter候補を命名規則のみで決定します。",
                    file=sys.stderr,
                )

    # list(set(candidates)) で重複を除去する
    # （方式1と方式2の両方で "getType" が追加された場合に1つにまとめる）
    # set() は順序を保証しないため順序が毎回変わる可能性があるが、
    # track_getter_calls() が全ファイルを検索するため順序は結果に影響しない
    return list(set(candidates))


def track_getter_calls(
    getter_name: str,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """プロジェクト全体で getter 呼び出し箇所を検索し、間接（getter経由）レコードを生成する。

    【検索パターン】
        r'\b' + getter_name + r'\s*\('
        例: getter_name="getType" → r'\bgetType\s*\('
        → "getType(" にも "getType (" にもマッチする（\s* でスペースを許容）
        → "myGetType(" には \b（単語境界）でマッチしない

    【false positive について】
        クラスを絞らずプロジェクト全体を検索するため、
        全く別のクラスが持つ同名メソッド（例: 別クラスの getType()）も検出される。
        これは仕様上許容された誤検出（見逃しより網羅性を優先する設計）。

    Args:
        getter_name: 追跡する getter メソッド名（例: "getType"）
        source_dir:  Java ソースのルートディレクトリ
        origin:      フィールド定義の直接参照レコード
        stats:       処理統計

    Returns:
        間接（getter経由）参照 GrepRecord のリスト
    """
    # getter_name() の呼び出しパターン（単語境界 + 開き括弧）
    # re.escape() で getter_name 内の特殊文字をエスケープ
    pattern = re.compile(r'\b' + re.escape(getter_name) + r'\s*\(')
    records: list[GrepRecord] = []

    # プロジェクト全体の全 .java ファイルを対象に検索する
    for java_file in sorted(source_dir.rglob("*.java")):
        try:
            lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
        except Exception:
            stats.encoding_errors.append(str(java_file))
            continue

        filepath_str = str(java_file)

        # enumerate(lines, start=1) で 1-indexed の行番号を振りながらイテレート
        for i, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue

            code = line.strip()
            usage_type = classify_usage(
                code=code,
                filepath=filepath_str,
                lineno=i,
                source_dir=source_dir,
                stats=stats,
            )
            records.append(GrepRecord(
                keyword=origin.keyword,
                ref_type=RefType.GETTER.value,   # "間接（getter経由）"
                usage_type=usage_type,
                filepath=filepath_str,
                lineno=str(i),
                code=code,
                src_var=getter_name,             # 経由した getter 名（例: "getType"）
                src_file=origin.filepath,        # フィールドが定義されていたファイル
                src_lineno=origin.lineno,        # フィールドが定義されていた行番号
            ))

    return records


# ============================================================================
# F-05: TsvWriter
# ─── 結果レコードをソートして UTF-8 BOM 付き TSV に書き出す ──────────────────
# ============================================================================

def write_tsv(records: list[GrepRecord], output_path: Path) -> None:
    """GrepRecord のリストを UTF-8 BOM 付き TSV ファイルとして書き出す。

    【ソート順】
        第1キー: keyword（検索文言）
        第2キー: filepath（ファイルパス）
        第3キー: lineno（行番号・数値順）

    【UTF-8 BOM について】
        encoding="utf-8-sig" は「UTF-8 + BOM（Byte Order Mark）」を意味する。
        BOM = ファイル先頭に付加される 3バイト（EF BB BF）のマーク。
        Windows の Excel はこれがないと UTF-8 を認識できず日本語が文字化けする。

    【newline="" について】
        csv モジュールは改行を自前で管理する。
        newline="" を指定しないと OS の改行変換と csv の改行変換が二重にかかり
        \r\r\n のような二重改行が発生してしまう。

    Args:
        records:     出力する GrepRecord のリスト
        output_path: 出力先 TSV ファイルのパス
    """
    # 出力先ディレクトリが存在しない場合は自動作成する
    # parents=True  = 中間ディレクトリも含めて作成（Java の Files.createDirectories() 相当）
    # exist_ok=True = すでに存在してもエラーにしない
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # sorted() でソートした新しいリストを作る（元の records は変更しない）。
    # key=lambda r: (...) でソートキーを指定する（Java の Comparator に相当）。
    # タプル (a, b, c) を返すと「a が同値なら b を比較、b も同値なら c を比較」という複合ソート。
    sorted_records = sorted(
        records,
        key=lambda r: (
            r.keyword,                                          # 第1キー: キーワード
            r.filepath,                                         # 第2キー: ファイルパス
            int(r.lineno) if r.lineno.isdigit() else 0,        # 第3キー: 行番号（数値順）
            # 【なぜ int() 変換が必要か】
            #   lineno は str 型で保持している。str のまま比較すると辞書順になり
            #   "10" < "2" という逆転が発生する。int() に変換することで正しい数値順になる。
            #   isdigit() で数字かどうかを確認してから int() 変換する（安全のため）。
        ),
    )

    # UTF-8 BOM 付きで TSV ファイルを開く
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        # delimiter="\t" でタブ区切り（TSV）にする
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(_TSV_HEADERS)  # 1行目にヘッダーを書き出す
        for r in sorted_records:
            # GrepRecord の各フィールドを列順に並べて書き出す
            writer.writerow([
                r.keyword,    # 文言
                r.ref_type,   # 参照種別
                r.usage_type, # 使用タイプ
                r.filepath,   # ファイルパス
                r.lineno,     # 行番号
                r.code,       # コード行
                r.src_var,    # 参照元変数名（直接参照の場合は空文字）
                r.src_file,   # 参照元ファイル（直接参照の場合は空文字）
                r.src_lineno, # 参照元行番号（直接参照の場合は空文字）
            ])


# ============================================================================
# F-06: Reporter
# ─── 処理完了後のサマリを標準出力に表示する ─────────────────────────────────
# ============================================================================

def print_report(stats: ProcessStats, processed_files: list[str]) -> None:
    """処理サマリを標準出力に表示する。全ファイル処理完了後に1回だけ呼ばれる。

    表示内容:
        - 処理したファイル名のリスト
        - 総行数 / 有効行数 / スキップ行数
        - AST フォールバックが発生したファイル（あれば）
        - エンコーディングエラーが発生したファイル（あれば）

    Args:
        stats:           ProcessStats インスタンス（全処理を通じて蓄積された統計）
        processed_files: 処理した .grep ファイル名のリスト
    """
    print("\n--- 処理完了 ---")
    # ', '.join(processed_files) はリストをカンマ区切り文字列に結合する
    # Java の String.join(", ", list) と同じだが引数の順序が逆（区切り文字.join(リスト)）
    print(f"処理ファイル: {', '.join(processed_files)}")
    print(
        f"総行数: {stats.total_lines}  "
        f"有効: {stats.valid_lines}  "
        f"スキップ: {stats.skipped_lines}"
    )

    # Python では空リストは bool として False、要素があれば True と評価される
    # if stats.fallback_files: は Java の if (!list.isEmpty()) { に相当
    if stats.fallback_files:
        print(f"ASTフォールバック ({len(stats.fallback_files)} 件):")
        for f in stats.fallback_files:
            print(f"  {f}")

    if stats.encoding_errors:
        print(f"エンコーディングエラー ({len(stats.encoding_errors)} 件):")
        for f in stats.encoding_errors:
            print(f"  {f}")


# ============================================================================
# CLI: argparse + main()
# ─── コマンドライン引数の解析と全処理の統括 ──────────────────────────────────
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """CLI オプションのパーサーを構築して返す。

    【なぜ main() 内に書かずに関数として分けるのか】
        main() の中に argparse の定義を全部書いてしまうと、
        テストから引数を直接渡してパーサーだけを検証する単体テストが書けなくなる。
        関数に分けることで `parser.parse_args(["--source-dir", "/tmp"])` と
        テスト側が任意の引数を渡してパーサーの動作を独立してテストできる。

    Returns:
        設定済みの ArgumentParser インスタンス
    """
    parser = argparse.ArgumentParser(
        description="Java grep結果 自動分類・使用箇所洗い出しツール"
    )
    # required=True で必須引数（指定しないとエラー）
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Javaソースコードのルートディレクトリ",
    )
    # default= でデフォルト値を設定（指定しない場合は "input" が使われる）
    parser.add_argument(
        "--input-dir",
        default="input",
        help="grep結果ファイルの配置ディレクトリ（デフォルト: input/）",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="TSV出力先ディレクトリ（デフォルト: output/）",
    )
    return parser


def main() -> None:
    """エントリーポイント。argparse でオプションを解析し、全処理を統括する。

    処理フロー:
        1. CLI 引数を解析してディレクトリパスを取得
        2. ディレクトリの存在確認（エラーなら sys.exit(1) で終了）
        3. input/ ディレクトリから .grep ファイルを一覧取得
        4. 各 .grep ファイルについて:
           a. process_grep_file() で直接参照を取得・分類（第1段階）
           b. 定数定義・変数代入の行から間接参照を追跡（第2段階）
           c. フィールドの getter 呼び出しを追跡（第3段階）
           d. write_tsv() で TSV 出力
        5. print_report() でサマリ表示
    """
    parser = build_parser()
    # parse_args() は sys.argv[1:]（コマンドライン引数）を解析して Namespace オブジェクトを返す
    # args.source_dir、args.input_dir、args.output_dir としてアクセスできる
    args = parser.parse_args()

    # 文字列パスを Path オブジェクトに変換する（以降はパス操作が楽になる）
    source_dir = Path(args.source_dir)
    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # ─── 入力ディレクトリの検証 ────────────────────────────────────────────────
    # .exists() でパスが存在するか確認。.is_dir() でディレクトリかどうかを確認。
    if not source_dir.exists() or not source_dir.is_dir():
        print(
            f"エラー: --source-dir で指定したディレクトリが存在しません: {source_dir}",
            file=sys.stderr,  # エラーメッセージは標準エラー出力（stderr）に出す
        )
        sys.exit(1)  # 終了コード1でプロセスを終了（非正常終了）

    if not input_dir.exists() or not input_dir.is_dir():
        print(
            f"エラー: --input-dir で指定したディレクトリが存在しません: {input_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ─── .grep ファイルの一覧取得 ───────────────────────────────────────────────
    # Path.glob("*.grep") は input_dir 直下の .grep ファイルをジェネレータで返す
    # sorted() でアルファベット順に並べてリストに変換する
    grep_files = sorted(input_dir.glob("*.grep"))
    if not grep_files:
        print("エラー: input/ディレクトリにgrep結果ファイルがありません", file=sys.stderr)
        sys.exit(1)

    # 全処理を通じた統計を収集するオブジェクト（各関数に渡して蓄積させる）
    stats = ProcessStats()
    processed_files: list[str] = []  # 処理完了したファイル名のリスト

    try:
        for grep_path in grep_files:
            # Path.stem = 拡張子を除いたファイル名
            # "input/SAMPLE.grep" の stem → "SAMPLE"
            keyword = grep_path.stem

            # ─── 第1段階: 直接参照の取得と使用タイプ分類 ─────────────────────────
            direct_records = process_grep_file(grep_path, keyword, source_dir, stats)

            # list(direct_records) でコピーを作る。
            # 後で extend() で間接参照レコードを追加していくため、
            # 元の direct_records は変えずに別のリストとして管理する。
            all_records: list[GrepRecord] = list(direct_records)

            # ─── 第2・第3段階: 間接参照・getter経由参照の追跡 ──────────────────────
            for record in direct_records:
                # 間接追跡の起点になるのは「定数定義」「変数代入」の行だけ。
                # 条件判定・return文・メソッド引数は「文言が直接使われているだけ」のため追跡不要。
                if record.usage_type not in (
                    UsageType.CONSTANT.value, UsageType.VARIABLE.value
                ):
                    continue

                # コード行から変数名を抽出する（例: "SAMPLE_CODE"、"type"）
                var_name = extract_variable_name(record.code, record.usage_type)
                if not var_name:
                    # 変数名が抽出できなかった場合はスキップ
                    continue

                # 変数のスコープ（追跡範囲）を決定する
                scope = determine_scope(
                    record.usage_type, record.code,
                    record.filepath, source_dir, int(record.lineno),
                )

                if scope == "project":
                    # 定数（static final）→ プロジェクト全体で追跡
                    all_records.extend(
                        track_constant(var_name, source_dir, record, stats)
                    )

                elif scope == "class":
                    # フィールド → 同一クラス内で追跡 + getter 呼び出しも追跡
                    class_file = _resolve_java_file(record.filepath, source_dir)
                    if class_file:
                        # フィールドの直接参照（クラス内のメソッドからの参照）を追跡
                        indirect = track_field(var_name, class_file, record, source_dir, stats)
                        all_records.extend(indirect)

                        # getter 経由の参照も追跡する
                        # find_getter_names() で getter 候補名を取得してから
                        # track_getter_calls() でプロジェクト全体を検索する
                        for getter_name in find_getter_names(var_name, class_file):
                            all_records.extend(
                                track_getter_calls(getter_name, source_dir, record, stats)
                            )

                elif scope == "method":
                    # ローカル変数 → 同一メソッドの行範囲内で追跡
                    method_scope = _get_method_scope(
                        record.filepath, source_dir, int(record.lineno)
                    )
                    if method_scope:
                        all_records.extend(
                            track_local(var_name, method_scope, record, source_dir, stats)
                        )

            # ─── 出力 ─────────────────────────────────────────────────────────────
            output_path = output_dir / f"{keyword}.tsv"
            write_tsv(all_records, output_path)

            processed_files.append(grep_path.name)
            direct_count   = len(direct_records)
            indirect_count = len(all_records) - direct_count
            print(
                f"  {grep_path.name} → {output_path} "
                f"(直接: {direct_count} 件, 間接: {indirect_count} 件)"
            )

    except Exception as e:
        # 予期しない例外（バグ等）は最外層でキャッチしてメッセージを出して終了
        # 終了コード2は「予期しないエラー」を示す慣習
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    # 全処理完了後にサマリを表示する
    print_report(stats, processed_files)


# ============================================================================
# エントリーポイント
# ============================================================================
# `if __name__ == "__main__":` は「このファイルが直接実行された場合のみ main() を呼ぶ」という意味。
# `import analyze` として他のファイルからインポートされた場合は main() は実行されない。
# テストファイルが import analyze と書いた場合に main() が走らないようにするための慣用句。
if __name__ == "__main__":
    main()
