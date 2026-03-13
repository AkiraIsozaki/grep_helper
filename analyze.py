"""Java grep結果 自動分類・使用箇所洗い出しツール

grep結果ファイル（input/*.grep）を読み込み、Java AST解析によって
使用タイプを分類し、UTF-8 BOM付きTSVに出力する。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import javalang
    _JAVALANG_AVAILABLE = True
except ImportError:
    _JAVALANG_AVAILABLE = False

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 使用タイプ分類パターン（優先度順・モジュールレベルでプリコンパイル）
USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'@\w+\s*\('),                                  "アノテーション"),
    (re.compile(r'\bstatic\s+final\b'),                         "定数定義"),
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\.equals\s*\(|[!=]='), "条件判定"),
    (re.compile(r'\breturn\b'),                                  "return文"),
    (re.compile(r'\b\w[\w<>\[\]]*\s+\w+\s*='),                 "変数代入"),
    (re.compile(r'\w+\s*\('),                                    "メソッド引数"),
]

# バイナリ通知行を検出するパターン
_BINARY_PATTERN = re.compile(r'^Binary file .+ matches$')

# grep行をパースするパターン: filepath:lineno:code
# Windowsパス（C:\path\file.java:10:code）対応のため maxsplit=1 を使用
_GREP_LINE_PATTERN = re.compile(r':(\d+):')

# ---------------------------------------------------------------------------
# Enum / データモデル
# ---------------------------------------------------------------------------


class RefType(Enum):
    """参照種別。"""
    DIRECT = "直接"
    INDIRECT = "間接"
    GETTER = "間接（getter経由）"


class UsageType(Enum):
    """使用タイプ（7種）。"""
    ANNOTATION = "アノテーション"
    CONSTANT = "定数定義"
    VARIABLE = "変数代入"
    CONDITION = "条件判定"
    RETURN = "return文"
    ARGUMENT = "メソッド引数"
    OTHER = "その他"


@dataclass(frozen=True)
class GrepRecord:
    """分析結果の1件を表すイミュータブルなデータモデル。"""
    keyword: str        # 検索した文言（入力ファイル名から取得）
    ref_type: str       # 参照種別（RefType.value）
    usage_type: str     # 使用タイプ（UsageType.value）
    filepath: str       # 該当行のファイルパス
    lineno: str         # 該当行の行番号
    code: str           # 該当行のコード（前後の空白はtrim済み）
    src_var:    str = ""   # 間接参照の場合：経由した変数/定数名
    src_file:   str = ""   # 間接参照の場合：変数/定数が定義されたファイルパス
    src_lineno: str = ""   # 間接参照の場合：変数/定数が定義された行番号


@dataclass
class ProcessStats:
    """処理統計。"""
    total_lines:     int = 0
    valid_lines:     int = 0
    skipped_lines:   int = 0
    fallback_files:  list[str] = field(default_factory=list)
    encoding_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ASTキャッシュ（モジュールレベル・シングルトン）
# ---------------------------------------------------------------------------

# None = javalang パースエラーが発生したファイル（フォールバック対象）
_ast_cache: dict[str, object | None] = {}


# ---------------------------------------------------------------------------
# F-01: GrepParser
# ---------------------------------------------------------------------------

def parse_grep_line(line: str) -> dict | None:
    """grep結果の1行をパースする。不正行はNoneを返す。

    対応フォーマット: 'filepath:lineno:code'
    Windowsパス対応: re.split(r':(\\d+):', line, maxsplit=1) を使用

    Args:
        line: grep結果の1行（末尾の改行は呼び出し元でstripされていること）

    Returns:
        {'filepath': str, 'lineno': str, 'code': str} または None
    """
    stripped = line.rstrip('\n\r')

    # 空行スキップ
    if not stripped.strip():
        return None

    # バイナリ通知行スキップ（例: "Binary file xxx matches"）
    if _BINARY_PATTERN.match(stripped):
        return None

    # filepath:lineno:code の形式でパース
    # maxsplit=1 でWindowsパス（C:\...）の最初の数字コロンで分割
    parts = _GREP_LINE_PATTERN.split(stripped, maxsplit=1)
    if len(parts) != 3:
        return None

    filepath, lineno, code = parts
    if not filepath or not lineno:
        return None

    return {
        "filepath": filepath,
        "lineno":   lineno,
        "code":     code.strip(),
    }


def process_grep_file(
    path: Path,
    keyword: str,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """grepファイル全行を処理し、第1段階（直接参照）レコードのリストを返す。

    Args:
        path:       処理する .grep ファイルのパス
        keyword:    検索文言（入力ファイル名から取得）
        source_dir: Javaソースコードのルートディレクトリ
        stats:      処理統計（更新される）

    Returns:
        直接参照 GrepRecord のリスト
    """
    # 500MB超の場合は警告
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > 500:
        print(
            f"警告: {path.name} のサイズが {file_size_mb:.1f}MB を超えています。処理に時間がかかる場合があります。",
            file=sys.stderr,
        )

    records: list[GrepRecord] = []

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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


# ---------------------------------------------------------------------------
# F-02: UsageClassifier
# ---------------------------------------------------------------------------

def get_ast(filepath: str, source_dir: Path) -> object | None:
    """Javaファイルを解析してASTを返す。キャッシュを利用して再解析を省略する。

    Args:
        filepath:   Javaファイルのパス（相対または絶対）
        source_dir: Javaソースのルートディレクトリ

    Returns:
        javalang の CompilationUnit、またはパースエラー時は None
    """
    if not _JAVALANG_AVAILABLE:
        return None

    cache_key = str(filepath)
    if cache_key in _ast_cache:
        return _ast_cache[cache_key]

    # source_dir / filepath または filepath 単体で試みる
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
        # javalang.parser.JavaSyntaxError を含む全例外をフォールバック扱い
        _ast_cache[cache_key] = None

    return _ast_cache[cache_key]


def classify_usage_regex(code: str) -> str:
    """正規表現で使用タイプを分類する（フォールバック専用）。

    優先度順に評価: アノテーション > 定数定義 > 条件判定 >
                   return文 > 変数代入 > メソッド引数 > その他

    Args:
        code: 分類対象のコード行（前後の空白はtrim済みを推奨）

    Returns:
        UsageType の value 文字列（7種のいずれか）
    """
    stripped = code.strip()
    for pattern, usage_type in USAGE_PATTERNS:
        if pattern.search(stripped):
            return usage_type
    return UsageType.OTHER.value


def classify_usage(
    code: str,
    filepath: str,
    lineno: int,
    source_dir: Path,
    stats: ProcessStats,
) -> str:
    """コード行を解析し、使用タイプ文字列を返す。

    javalangによるAST解析を試み、パースエラーの場合は
    正規表現フォールバックで継続する。

    Args:
        code:       分類対象のコード行（前後の空白はtrim済み）
        filepath:   Javaファイルのパス（AST解析用）
        lineno:     対象行の行番号（AST解析用）
        source_dir: Javaソースのルートディレクトリ
        stats:      処理統計（フォールバック件数の記録用）

    Returns:
        UsageType の value 文字列（7種のいずれか）
    """
    tree = get_ast(filepath, source_dir)

    if tree is None:
        # AST解析失敗またはjavalang未インストール → 正規表現フォールバック
        if _JAVALANG_AVAILABLE and filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)
        return classify_usage_regex(code)

    # ASTが利用可能な場合はノードの行番号からタイプを判定
    try:
        usage = _classify_by_ast(tree, lineno)
        if usage is not None:
            return usage
    except Exception:
        # AST走査中の予期しない例外 → フォールバック対象として記録して継続
        if filepath not in stats.fallback_files:
            stats.fallback_files.append(filepath)

    # AST解析で判定できなかった場合は正規表現フォールバック
    return classify_usage_regex(code)


def _classify_by_ast(tree: object, lineno: int) -> str | None:
    """ASTノードの行番号から使用タイプを判定する。

    Args:
        tree:   javalang の CompilationUnit
        lineno: 対象行の行番号

    Returns:
        UsageType の value 文字列、または判定不能の場合は None
    """
    if not _JAVALANG_AVAILABLE:
        return None

    for _, node in tree:
        if not hasattr(node, 'position') or node.position is None:
            continue
        if node.position.line != lineno:
            continue

        # アノテーション
        if isinstance(node, javalang.tree.Annotation):
            return UsageType.ANNOTATION.value

        # フィールド・ローカル変数宣言（定数定義・変数代入）
        if isinstance(node, (
            javalang.tree.FieldDeclaration,
            javalang.tree.LocalVariableDeclaration,
        )):
            modifiers = getattr(node, 'modifiers', set()) or set()
            if 'static' in modifiers and 'final' in modifiers:
                return UsageType.CONSTANT.value
            return UsageType.VARIABLE.value

        # if / while 文（条件判定）
        if isinstance(node, (
            javalang.tree.IfStatement,
            javalang.tree.WhileStatement,
        )):
            return UsageType.CONDITION.value

        # return 文
        if isinstance(node, javalang.tree.ReturnStatement):
            return UsageType.RETURN.value

        # メソッド呼び出し（メソッド引数）
        if isinstance(node, (
            javalang.tree.MethodInvocation,
            javalang.tree.ClassCreator,
        )):
            return UsageType.ARGUMENT.value

    return None


# ---------------------------------------------------------------------------
# F-03: IndirectTracker
# ---------------------------------------------------------------------------

# フィールド宣言判定用パターン
_FIELD_DECL_PATTERN = re.compile(
    r'^(private|protected|public|static|final|\s)*\s+\w[\w<>\[\]]*\s+\w+\s*[=;]'
)


def determine_scope(
    usage_type: str,
    code: str,
    filepath: str = "",
    source_dir: Path | None = None,
    lineno: int = 0,
) -> str:
    """変数の種類に応じた追跡スコープを返す。

    javalang が利用可能な場合は AST の FieldDeclaration / LocalVariableDeclaration
    ノードで判定するため、パッケージプライベートフィールド（修飾子なし）も正しく
    "class" と判定できる。AST が使えない場合は正規表現フォールバック。

    Args:
        usage_type:  使用タイプ文字列（UsageType.value）
        code:        変数定義のコード行
        filepath:    Javaファイルのパス（AST判定に使用。省略時はフォールバック）
        source_dir:  Javaソースのルートディレクトリ（AST判定に使用）
        lineno:      対象行の行番号（AST判定に使用）

    Returns:
        "project"（定数）/ "class"（フィールド）/ "method"（ローカル変数）
    """
    if usage_type == UsageType.CONSTANT.value:
        return "project"

    # AST が利用可能な場合は FieldDeclaration ノードで判定
    # （パッケージプライベートフィールドも正しく検出できる）
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

    # ASTが使えない場合は正規表現フォールバック
    stripped = code.strip()
    if _FIELD_DECL_PATTERN.match(stripped):
        return "class"
    return "method"


def extract_variable_name(code: str, usage_type: str) -> str | None:  # noqa: ARG001
    """定数/変数の名前をコード行から抽出する。

    左辺（= より前）の最後の識別子を変数名とみなす。
    例: "public static final String CODE = ..." → "CODE"
    例: "String msg = CODE;" → "msg"
    例: "private String type;" → "type"

    Args:
        code:       変数定義のコード行
        usage_type: 使用タイプ文字列（現在は未使用だがインターフェース上受け取る）

    Returns:
        変数名文字列、または抽出できない場合は None
    """
    stripped = code.strip().rstrip(';')
    # = の左辺のみを対象にする
    decl_part = stripped.split('=')[0].strip()
    # 最後のトークン（識別子）が変数名
    tokens = decl_part.split()
    if len(tokens) >= 2:
        # 末尾トークンから記号を除去して返す
        name = tokens[-1].strip('[];(){}<>')
        if name.isidentifier():
            return name
    return None


def _resolve_java_file(filepath: str, source_dir: Path) -> Path | None:
    """filepathをPathオブジェクトに解決する。

    Args:
        filepath:   Javaファイルのパス（相対または絶対）
        source_dir: Javaソースのルートディレクトリ

    Returns:
        存在する Path、または解決できない場合は None
    """
    candidate = Path(filepath)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    resolved = source_dir / filepath
    if resolved.exists():
        return resolved
    return None


def _get_method_scope(
    filepath: str, source_dir: Path, lineno: int
) -> tuple[int, int] | None:
    """指定行を含むメソッドの行範囲を返す（内部ヘルパー）。

    javalang でメソッド開始行を取得し、ブレースカウンタで終了行を特定する。
    javalang はノードの終了行を提供しないため、ブレースカウンタ方式を採用。

    Args:
        filepath:   Javaファイルのパス
        source_dir: Javaソースのルートディレクトリ
        lineno:     対象行の行番号

    Returns:
        (start_line, end_line) のタプル、または特定不能の場合は None
    """
    if not _JAVALANG_AVAILABLE:
        return None

    tree = get_ast(filepath, source_dir)
    if tree is None:
        return None

    # メソッド開始行をすべて収集してソート
    method_starts: list[int] = []
    try:
        for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
            if method_decl.position:
                method_starts.append(method_decl.position.line)
    except Exception:
        return None

    if not method_starts:
        return None

    method_starts.sort()

    # lineno を含むメソッドの開始行を特定（lineno 以下で最大のもの）
    method_start = None
    for start in method_starts:
        if start <= lineno:
            method_start = start

    if method_start is None:
        return None

    # ソースを読み込んでブレースカウンタでメソッド終了行を探す
    java_file = _resolve_java_file(filepath, source_dir)
    if java_file is None:
        return None

    try:
        lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
    except Exception:
        return None

    brace_count = 0
    found_open = False
    for i, line in enumerate(lines[method_start - 1:], start=method_start):
        brace_count += line.count('{') - line.count('}')
        if not found_open and brace_count > 0:
            found_open = True
        if found_open and brace_count <= 0:
            return (method_start, i)

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
    """行リストから var_name を検索してGrepRecordを生成する（内部ヘルパー）。

    Args:
        lines:              検索対象の行リスト（0-indexed）
        var_name:           検索する変数名（単語境界マッチ）
        start_line:         lines[0] に対応する行番号（1-indexed）
        origin:             間接参照元の直接参照レコード
        source_dir:         Javaソースのルートディレクトリ
        ref_type:           参照種別（RefType.INDIRECT.value 等）
        stats:              処理統計
        filepath_for_record: GrepRecord に記録するファイルパス文字列

    Returns:
        生成した GrepRecord のリスト
    """
    pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
    records: list[GrepRecord] = []

    for idx, line in enumerate(lines):
        current_lineno = start_line + idx
        # 定義行（origin）はスキップ
        if (filepath_for_record == origin.filepath
                and str(current_lineno) == origin.lineno):
            continue
        if not pattern.search(line):
            continue

        code = line.strip()
        usage_type = classify_usage(
            code=code,
            filepath=filepath_for_record,
            lineno=current_lineno,
            source_dir=source_dir,
            stats=stats,
        )
        records.append(GrepRecord(
            keyword=origin.keyword,
            ref_type=ref_type,
            usage_type=usage_type,
            filepath=filepath_for_record,
            lineno=str(current_lineno),
            code=code,
            src_var=var_name,
            src_file=origin.filepath,
            src_lineno=origin.lineno,
        ))

    return records


def track_constant(
    var_name: str,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """static final の定数をプロジェクト全体で追跡する。

    Args:
        var_name:   追跡する定数名
        source_dir: Javaソースのルートディレクトリ
        origin:     定数定義の直接参照レコード
        stats:      処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    records: list[GrepRecord] = []

    for java_file in sorted(source_dir.rglob("*.java")):
        try:
            lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
        except Exception:
            stats.encoding_errors.append(str(java_file))
            continue

        filepath_str = str(java_file)
        records.extend(_search_in_lines(
            lines=lines,
            var_name=var_name,
            start_line=1,
            origin=origin,
            source_dir=source_dir,
            ref_type=RefType.INDIRECT.value,
            stats=stats,
            filepath_for_record=filepath_str,
        ))

    return records


def track_field(
    var_name: str,
    class_file: Path,
    origin: GrepRecord,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """フィールドを同一クラス内で追跡する。

    Args:
        var_name:   追跡するフィールド名
        class_file: フィールドが定義されたJavaファイル
        origin:     フィールド定義の直接参照レコード
        source_dir: Javaソースのルートディレクトリ
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
        start_line=1,
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
    """ローカル変数を同一メソッド内で追跡する。

    Args:
        var_name:     追跡するローカル変数名
        method_scope: (開始行番号, 終了行番号) のタプルでメソッドの行範囲を指定
        origin:       変数定義の直接参照レコード
        source_dir:   Javaソースのルートディレクトリ
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
    # 0-indexed スライス: lines[start-1 : end]
    method_lines = all_lines[start_line - 1:end_line]

    return _search_in_lines(
        lines=method_lines,
        var_name=var_name,
        start_line=start_line,
        origin=origin,
        source_dir=source_dir,
        ref_type=RefType.INDIRECT.value,
        stats=stats,
        filepath_for_record=origin.filepath,
    )


# ---------------------------------------------------------------------------
# F-04: GetterTracker
# ---------------------------------------------------------------------------

def find_getter_names(field_name: str, class_file: Path) -> list[str]:
    """クラスファイルからgetterメソッド名の候補リストを返す。

    2方式を併用:
    1. 命名規則: field_name="type" → "getType"
    2. return文解析: `return field_name;` しているメソッドを全て検出（非標準命名も対象）

    Args:
        field_name: フィールド名
        class_file: フィールドが定義されたJavaファイル

    Returns:
        getter候補名の重複なしリスト
    """
    candidates: list[str] = []

    # 方式1: 命名規則（field_name="type" → "getType"）
    getter_by_convention = "get" + field_name[0].upper() + field_name[1:]
    candidates.append(getter_by_convention)

    # 方式2: ASTからreturn文を解析（javalangのAST walk）
    if _JAVALANG_AVAILABLE:
        cache_key = str(class_file)
        # in 演算子でキー存在確認（.get() はNone値と未設定の区別ができないため）
        if cache_key not in _ast_cache:
            try:
                source = class_file.read_text(encoding="shift_jis", errors="replace")
                _ast_cache[cache_key] = javalang.parse.parse(source)
            except Exception:
                _ast_cache[cache_key] = None

        tree = _ast_cache[cache_key]
        if tree is not None:
            try:
                for _, method_decl in tree.filter(javalang.tree.MethodDeclaration):
                    for _, stmt in method_decl.filter(javalang.tree.ReturnStatement):
                        if (stmt.expression is not None
                                and hasattr(stmt.expression, 'member')
                                and stmt.expression.member == field_name):
                            candidates.append(method_decl.name)
            except Exception:
                # AST walk失敗時は方式1(命名規則)のみで継続
                print(
                    f"警告: {class_file} のAST walk中にエラーが発生しました。"
                    "getter候補を命名規則のみで決定します。",
                    file=sys.stderr,
                )

    return list(set(candidates))


def track_getter_calls(
    getter_name: str,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """プロジェクト全体でgetter呼び出し箇所を検索・AST分類する。

    false positive は許容（もれなく優先）。
    他クラスの同名getterが混入する可能性があるが仕様上許容。

    Args:
        getter_name: 追跡するgetterメソッド名
        source_dir:  Javaソースのルートディレクトリ
        origin:      フィールド定義の直接参照レコード
        stats:       処理統計

    Returns:
        間接（getter経由）参照 GrepRecord のリスト
    """
    # getter_name() の呼び出しパターン（単語境界 + 開き括弧）
    pattern = re.compile(r'\b' + re.escape(getter_name) + r'\s*\(')
    records: list[GrepRecord] = []

    for java_file in sorted(source_dir.rglob("*.java")):
        try:
            lines = java_file.read_text(encoding="shift_jis", errors="replace").splitlines()
        except Exception:
            stats.encoding_errors.append(str(java_file))
            continue

        filepath_str = str(java_file)
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
                ref_type=RefType.GETTER.value,
                usage_type=usage_type,
                filepath=filepath_str,
                lineno=str(i),
                code=code,
                src_var=getter_name,
                src_file=origin.filepath,
                src_lineno=origin.lineno,
            ))

    return records


# ---------------------------------------------------------------------------
# F-05: TsvWriter
# ---------------------------------------------------------------------------

# TSVヘッダー列定義
_TSV_HEADERS = [
    "文言", "参照種別", "使用タイプ", "ファイルパス", "行番号", "コード行",
    "参照元変数名", "参照元ファイル", "参照元行番号",
]


def write_tsv(records: list[GrepRecord], output_path: Path) -> None:
    """GrepRecordのリストをUTF-8 BOM付きTSVに出力する。

    ソート順: 文言 → ファイルパス → 行番号（昇順）
    output/ ディレクトリが存在しない場合は自動作成する。

    Args:
        records:     出力する GrepRecord のリスト
        output_path: 出力先 TSV ファイルのパス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # lineno は str 型のため int() 変換して数値ソート（str ソートだと "10" < "9" になるバグ防止）
    sorted_records = sorted(
        records,
        key=lambda r: (r.keyword, r.filepath, int(r.lineno) if r.lineno.isdigit() else 0),
    )

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(_TSV_HEADERS)
        for r in sorted_records:
            writer.writerow([
                r.keyword,
                r.ref_type,
                r.usage_type,
                r.filepath,
                r.lineno,
                r.code,
                r.src_var,
                r.src_file,
                r.src_lineno,
            ])


# ---------------------------------------------------------------------------
# F-06: Reporter
# ---------------------------------------------------------------------------

def print_report(stats: ProcessStats, processed_files: list[str]) -> None:
    """処理サマリを標準出力に出力する。全ファイル処理完了後に1回呼び出す。

    Args:
        stats:           処理統計
        processed_files: 処理した .grep ファイル名のリスト
    """
    print("\n--- 処理完了 ---")
    print(f"処理ファイル: {', '.join(processed_files)}")
    print(
        f"総行数: {stats.total_lines}  "
        f"有効: {stats.valid_lines}  "
        f"スキップ: {stats.skipped_lines}"
    )
    if stats.fallback_files:
        print(f"ASTフォールバック ({len(stats.fallback_files)} 件):")
        for f in stats.fallback_files:
            print(f"  {f}")
    if stats.encoding_errors:
        print(f"エンコーディングエラー ({len(stats.encoding_errors)} 件):")
        for f in stats.encoding_errors:
            print(f"  {f}")


# ---------------------------------------------------------------------------
# CLI: argparse + main()
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """CLIオプションのパーサーを構築して返す。"""
    parser = argparse.ArgumentParser(
        description="Java grep結果 自動分類・使用箇所洗い出しツール"
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Javaソースコードのルートディレクトリ",
    )
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
    """エントリーポイント。argparse でオプションを解析し、全処理を統括する。"""
    parser = build_parser()
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # 入力ディレクトリの検証
    if not source_dir.exists() or not source_dir.is_dir():
        print(
            f"エラー: --source-dir で指定したディレクトリが存在しません: {source_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not input_dir.exists() or not input_dir.is_dir():
        print(
            f"エラー: --input-dir で指定したディレクトリが存在しません: {input_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    # .grep ファイルを検出
    grep_files = sorted(input_dir.glob("*.grep"))
    if not grep_files:
        print(
            "エラー: input/ディレクトリにgrep結果ファイルがありません",
            file=sys.stderr,
        )
        sys.exit(1)

    stats = ProcessStats()
    processed_files: list[str] = []

    try:
        for grep_path in grep_files:
            keyword = grep_path.stem  # 拡張子なしのファイル名 = 検索文言

            # 第1段階: 直接参照の取得と分類
            direct_records = process_grep_file(grep_path, keyword, source_dir, stats)
            all_records: list[GrepRecord] = list(direct_records)

            # 第2・第3段階: 間接参照・getter経由参照の追跡
            for record in direct_records:
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
                    # 第2段階: 定数をプロジェクト全体で追跡
                    all_records.extend(
                        track_constant(var_name, source_dir, record, stats)
                    )

                elif scope == "class":
                    # 第2段階: フィールドを同一クラス内で追跡
                    class_file = _resolve_java_file(record.filepath, source_dir)
                    if class_file:
                        indirect = track_field(var_name, class_file, record, source_dir, stats)
                        all_records.extend(indirect)

                        # 第3段階: getter経由を追跡
                        for getter_name in find_getter_names(var_name, class_file):
                            all_records.extend(
                                track_getter_calls(getter_name, source_dir, record, stats)
                            )

                elif scope == "method":
                    # 第2段階: ローカル変数を同一メソッド内で追跡
                    method_scope = _get_method_scope(
                        record.filepath, source_dir, int(record.lineno)
                    )
                    if method_scope:
                        all_records.extend(
                            track_local(var_name, method_scope, record, source_dir, stats)
                        )

            # 出力
            output_path = output_dir / f"{keyword}.tsv"
            write_tsv(all_records, output_path)

            processed_files.append(grep_path.name)
            direct_count = len(direct_records)
            indirect_count = len(all_records) - direct_count
            print(f"  {grep_path.name} → {output_path} (直接: {direct_count} 件, 間接: {indirect_count} 件)")

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    print_report(stats, processed_files)


if __name__ == "__main__":
    main()
