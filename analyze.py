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
    parts = re.split(r':(\d+):', stripped, maxsplit=1)
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
        pass

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

    for path, node in tree:
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
            records = process_grep_file(grep_path, keyword, source_dir, stats)

            # 出力
            output_path = output_dir / f"{keyword}.tsv"
            write_tsv(records, output_path)

            processed_files.append(grep_path.name)
            print(f"  {grep_path.name} → {output_path} ({len(records)} 件)")

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    # 処理レポート（簡易版: F-06 Reporter は次ステップで実装）
    print("\n--- 処理完了 ---")
    print(f"処理ファイル: {', '.join(processed_files)}")
    print(f"総行数: {stats.total_lines}  有効: {stats.valid_lines}  スキップ: {stats.skipped_lines}")
    if stats.fallback_files:
        print(f"ASTフォールバック: {len(stats.fallback_files)} ファイル")
    if stats.encoding_errors:
        print(f"エンコーディングエラー: {len(stats.encoding_errors)} ファイル")


if __name__ == "__main__":
    main()
