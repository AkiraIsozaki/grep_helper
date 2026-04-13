"""Pro*C grep結果 自動分類・使用箇所洗い出しツール

grep結果ファイル（input/*.grep）を読み込み、正規表現ベースの分類によって
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
from typing import NamedTuple

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# Pro*C向け使用タイプ分類パターン（優先度順・モジュールレベルでプリコンパイル）
PROC_USAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bEXEC\s+SQL\b', re.IGNORECASE),               "EXEC SQL文"),
    (re.compile(r'^\s*#\s*define\b'),                              "#define定数定義"),
    (re.compile(r'\bif\s*\(|\bwhile\s*\(|\bstrcmp\s*\(|[!=]='),  "条件判定"),
    (re.compile(r'\breturn\b'),                                    "return文"),
    (re.compile(r'\b\w[\w\*]*\s+\*?\w+\s*(?:\[.*?\])?\s*[=;]'),  "変数代入"),
    (re.compile(r'\w+\s*\('),                                      "関数引数"),
]

# バイナリ通知行を検出するパターン
_BINARY_PATTERN = re.compile(r'^Binary file .+ matches$')

# grep行をパースするパターン: filepath:lineno:code
_GREP_LINE_PATTERN = re.compile(r':(\d+):')

# ファイル行キャッシュ上限
_MAX_FILE_CACHE_SIZE = 800

# ファイル行キャッシュ: filepath → lines（shift_jis, errors=replace）
_file_cache: dict[str, list[str]] = {}

# ---------------------------------------------------------------------------
# Enum / データモデル
# ---------------------------------------------------------------------------


class RefType(Enum):
    """参照種別。"""
    DIRECT = "直接"
    INDIRECT = "間接"


class GrepRecord(NamedTuple):
    """分析結果の1件を表すイミュータブルなデータモデル。"""
    keyword: str        # 検索した文言（入力ファイル名から取得）
    ref_type: str       # 参照種別（RefType.value）
    usage_type: str     # 使用タイプ
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
    encoding_errors: set[str] = field(default_factory=set)


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

    if not stripped.strip():
        return None

    if _BINARY_PATTERN.match(stripped):
        return None

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


def _read_source_file(path: Path, stats: ProcessStats) -> list[str]:
    """Pro*Cソースファイルをキャッシュ付きで読み込む。

    Args:
        path:  読み込むファイルのパス
        stats: 処理統計（エンコーディングエラー記録に使用）

    Returns:
        行のリスト（改行なし）。読み込みエラー時は空リスト。
    """
    key = str(path)
    if key in _file_cache:
        return _file_cache[key]

    if len(_file_cache) >= _MAX_FILE_CACHE_SIZE:
        _file_cache.pop(next(iter(_file_cache)))

    try:
        _file_cache[key] = path.read_text(
            encoding="shift_jis", errors="replace"
        ).splitlines()
    except Exception:
        stats.encoding_errors.add(key)
        _file_cache[key] = []

    return _file_cache[key]


def process_grep_file(
    path: Path,
    keyword: str,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """grepファイル全行を処理し、直接参照レコードのリストを返す。

    Args:
        path:       処理する .grep ファイルのパス
        keyword:    検索文言（入力ファイル名から取得）
        source_dir: Pro*Cソースコードのルートディレクトリ（未使用だが統一インターフェース）
        stats:      処理統計（更新される）

    Returns:
        直接参照 GrepRecord のリスト（usage_type は未設定 = ""）
    """
    records: list[GrepRecord] = []

    with open(path, encoding="cp932", errors="replace") as f:
        for line in f:
            stats.total_lines += 1

            parsed = parse_grep_line(line)
            if parsed is None:
                stats.skipped_lines += 1
                continue

            records.append(GrepRecord(
                keyword=keyword,
                ref_type=RefType.DIRECT.value,
                usage_type="",
                filepath=parsed["filepath"],
                lineno=parsed["lineno"],
                code=parsed["code"],
            ))
            stats.valid_lines += 1

    return records


# ---------------------------------------------------------------------------
# F-02: ProcUsageClassifier
# ---------------------------------------------------------------------------

def classify_usage_proc(code: str) -> str:
    """コード行を正規表現で7種の使用タイプに分類する。

    PROC_USAGE_PATTERNS を優先度順に評価し、非マッチは「その他」を返す。

    Args:
        code: コード行（strip済みを推奨）

    Returns:
        使用タイプ文字列
    """
    for pattern, usage_type in PROC_USAGE_PATTERNS:
        if pattern.search(code):
            return usage_type
    return "その他"


# ---------------------------------------------------------------------------
# F-03: ProcIndirectTracker
# ---------------------------------------------------------------------------

def extract_define_name(code: str) -> str | None:
    """#define定義行から定数名を抽出する。

    Args:
        code: コード行

    Returns:
        定数名文字列、または抽出できない場合は None
    """
    m = re.match(r'^\s*#\s*define\s+(\w+)\s+', code)
    if m:
        return m.group(1)
    return None


_C_TYPE_PATTERN = re.compile(
    r'^\s*(?:(?:unsigned|signed|long|short|static|extern|const|volatile)\s+)*'
    r'(?:int|char|float|double|long|short|void|struct\s+\w+|\w+_t)\s*\*?\s+\*?\w+'
)


def extract_variable_name_proc(code: str) -> str | None:
    """C変数宣言行から変数名を抽出する。

    例: 'char localVar[] = "keyword";' → "localVar"
    例: 'char varName[256];' → "varName"

    EXEC SQL 行・複数トークンの非宣言行は None を返す。

    Args:
        code: コード行

    Returns:
        変数名文字列、または抽出できない場合は None
    """
    stripped = code.strip()

    # EXEC SQL 行は変数宣言ではない
    if re.match(r'^\s*EXEC\s+SQL\b', stripped, re.IGNORECASE):
        return None

    # C型宣言パターンに一致しない行は除外
    if not _C_TYPE_PATTERN.match(stripped):
        return None

    stripped = stripped.rstrip(';')
    # = の左辺のみ
    decl_part = stripped.split('=')[0].strip()
    # 配列サイズ [] を除去
    decl_part = re.sub(r'\[.*?\]', '', decl_part).strip()
    tokens = decl_part.split()
    if len(tokens) >= 2:
        name = tokens[-1].strip('*')
        if re.match(r'^\w+$', name):
            return name
    return None


def extract_host_var_name(code: str) -> str | None:
    """DECLARE SECTION内の変数宣言行から変数名を抽出する。

    例: 'char hostVar[256];' → "hostVar"
    例: 'int count;' → "count"

    Args:
        code: コード行

    Returns:
        変数名文字列、または抽出できない場合は None
    """
    # Cの型宣言パターン: type varName[...]; or type varName;
    m = re.match(r'^\s*\w[\w\s\*]*\s+(\w+)\s*(?:\[.*?\])?\s*;', code)
    if m:
        candidate = m.group(1)
        # 予約語を除外
        if candidate not in ('int', 'char', 'long', 'short', 'float', 'double',
                              'unsigned', 'signed', 'void', 'struct', 'union',
                              'typedef', 'static', 'extern', 'const', 'volatile'):
            return candidate
    return None


def _find_function_scope(lines: list[str], lineno: int) -> tuple[int, int]:
    """指定行番号を含む関数のスコープ範囲を返す。

    指定行から上方向に `{` を探し、ブレースの対応で関数の終端を特定する。

    Args:
        lines:  ファイルの全行リスト（0-indexed）
        lineno: 対象行の行番号（1-indexed）

    Returns:
        (start_lineno, end_lineno) の1-indexedタプル。特定失敗時は (1, len(lines))
    """
    idx = lineno - 1  # 0-indexed

    # 上方向に関数先頭の { を探す
    brace_count = 0
    func_start_idx = None
    for i in range(idx, -1, -1):
        line = lines[i]
        brace_count += line.count('{') - line.count('}')
        if brace_count > 0:
            func_start_idx = i
            break

    if func_start_idx is None:
        return (1, len(lines))

    # 関数先頭から下方向にブレースを追跡して終端を探す
    brace_count = 0
    found_open = False
    for i in range(func_start_idx, len(lines)):
        line = lines[i]
        brace_count += line.count('{') - line.count('}')
        if not found_open and brace_count > 0:
            found_open = True
        if found_open and brace_count <= 0:
            return (func_start_idx + 1, i + 1)

    return (func_start_idx + 1, len(lines))


def _detect_host_var_scope(lines: list[str]) -> list[tuple[int, int]]:
    """ファイル全体をスキャンしてDECLARE SECTIONの範囲リストを返す。

    Args:
        lines: ファイルの全行リスト（0-indexed）

    Returns:
        (開始行番号, 終了行番号) の1-indexedタプルのリスト
    """
    ranges: list[tuple[int, int]] = []
    begin_pat = re.compile(r'\bEXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION\b', re.IGNORECASE)
    end_pat = re.compile(r'\bEXEC\s+SQL\s+END\s+DECLARE\s+SECTION\b', re.IGNORECASE)

    start = None
    for i, line in enumerate(lines, start=1):
        if begin_pat.search(line):
            start = i
        elif end_pat.search(line) and start is not None:
            ranges.append((start, i))
            start = None

    return ranges


def track_define(
    var_name: str,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """#define定数名をプロジェクト全体（.pc / .h）で追跡する。

    Args:
        var_name:   追跡する定数名
        source_dir: Pro*Cプロジェクトのルートディレクトリ
        origin:     定数定義の直接参照レコード
        stats:      処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
    records: list[GrepRecord] = []

    for ext in ('*.pc', '*.h'):
        for src_file in sorted(source_dir.rglob(ext)):
            try:
                filepath_str = str(src_file.relative_to(source_dir))
            except ValueError:
                filepath_str = str(src_file)

            lines = _read_source_file(src_file, stats)
            if not lines:
                continue

            for i, line in enumerate(lines, start=1):
                if filepath_str == origin.filepath and str(i) == origin.lineno:
                    continue
                if not pattern.search(line):
                    continue

                code = line.strip()
                records.append(GrepRecord(
                    keyword=origin.keyword,
                    ref_type=RefType.INDIRECT.value,
                    usage_type=classify_usage_proc(code),
                    filepath=filepath_str,
                    lineno=str(i),
                    code=code,
                    src_var=var_name,
                    src_file=origin.filepath,
                    src_lineno=origin.lineno,
                ))

    return records


def track_variable(
    var_name: str,
    filepath: Path,
    lineno: int,
    source_dir: Path,
    origin: GrepRecord,
    stats: ProcessStats,
) -> list[GrepRecord]:
    """変数宣言をスコープに応じて追跡する。

    - DECLARE SECTION内: ホスト変数 → 同一ファイル全体で :var_name を検索
    - それ以外: ローカル変数 → 同一関数スコープ内で var_name を検索

    Args:
        var_name:   追跡する変数名
        filepath:   変数が定義されたファイルのパス
        lineno:     変数定義の行番号（1-indexed）
        source_dir: Pro*Cプロジェクトのルートディレクトリ
        origin:     変数定義の直接参照レコード
        stats:      処理統計

    Returns:
        間接参照 GrepRecord のリスト
    """
    lines = _read_source_file(filepath, stats)
    if not lines:
        return []

    try:
        filepath_str = str(filepath.relative_to(source_dir))
    except ValueError:
        filepath_str = str(filepath)

    # DECLARE SECTIONのスコープを検出
    declare_ranges = _detect_host_var_scope(lines)
    is_host_var = any(start <= lineno <= end for start, end in declare_ranges)

    records: list[GrepRecord] = []

    if is_host_var:
        # ホスト変数: 同一ファイル全体で :var_name を検索
        pattern = re.compile(r':\b' + re.escape(var_name) + r'\b')
        search_lines = lines
        start_line = 1
    else:
        # ローカル変数: 同一関数スコープ内を検索
        scope_start, scope_end = _find_function_scope(lines, lineno)
        pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
        search_lines = lines[scope_start - 1:scope_end]
        start_line = scope_start

    for idx, line in enumerate(search_lines):
        current_lineno = start_line + idx
        if filepath_str == origin.filepath and str(current_lineno) == origin.lineno:
            continue
        if not pattern.search(line):
            continue

        code = line.strip()
        records.append(GrepRecord(
            keyword=origin.keyword,
            ref_type=RefType.INDIRECT.value,
            usage_type=classify_usage_proc(code),
            filepath=filepath_str,
            lineno=str(current_lineno),
            code=code,
            src_var=var_name,
            src_file=origin.filepath,
            src_lineno=origin.lineno,
        ))

    return records


# ---------------------------------------------------------------------------
# F-04: TsvWriter
# ---------------------------------------------------------------------------

_TSV_HEADERS = [
    "文言", "参照種別", "使用タイプ", "ファイルパス", "行番号", "コード行",
    "参照元変数名", "参照元ファイル", "参照元行番号",
]


def write_tsv(records: list[GrepRecord], output_path: Path) -> None:
    """GrepRecordのリストをUTF-8 BOM付きTSVに出力する。

    ソート順: 文言 → ファイルパス → 行番号（昇順、行番号は数値ソート）
    output/ ディレクトリが存在しない場合は自動作成する。

    Args:
        records:     出力する GrepRecord のリスト
        output_path: 出力先 TSV ファイルのパス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _sort_key(r: GrepRecord) -> tuple:
        lineno_int = int(r.lineno) if r.lineno.isdigit() else 0
        if r.ref_type == RefType.DIRECT.value:
            return (r.keyword, r.filepath, lineno_int, 0, "", 0)
        else:
            src_lineno_int = int(r.src_lineno) if r.src_lineno.isdigit() else 0
            return (r.keyword, r.src_file, src_lineno_int, 1, r.filepath, lineno_int)

    records.sort(key=_sort_key)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(_TSV_HEADERS)
        for r in records:
            writer.writerow([
                r.keyword, r.ref_type, r.usage_type, r.filepath,
                r.lineno, r.code, r.src_var, r.src_file, r.src_lineno,
            ])


# ---------------------------------------------------------------------------
# F-05: Reporter
# ---------------------------------------------------------------------------

def print_report(stats: ProcessStats, processed_files: list[str]) -> None:
    """処理サマリを標準出力に出力する。

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
    if stats.encoding_errors:
        print(f"エンコーディングエラー ({len(stats.encoding_errors)} 件):")
        for f in sorted(stats.encoding_errors):
            print(f"  {f}")


# ---------------------------------------------------------------------------
# CLI: argparse + main()
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """CLIオプションのパーサーを構築して返す。"""
    parser = argparse.ArgumentParser(
        description="Pro*C grep結果 自動分類・使用箇所洗い出しツール"
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Pro*Cソースコードのルートディレクトリ",
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
            keyword = grep_path.stem

            # 第1段階: 直接参照のパース
            direct_records = process_grep_file(grep_path, keyword, source_dir, stats)

            # usage_type を分類
            classified: list[GrepRecord] = []
            for r in direct_records:
                classified.append(r._replace(usage_type=classify_usage_proc(r.code)))
            direct_records = classified

            all_records: list[GrepRecord] = list(direct_records)

            # 第2段階: 間接参照追跡
            for record in direct_records:
                if record.usage_type == "#define定数定義":
                    var_name = extract_define_name(record.code)
                    if var_name:
                        all_records.extend(
                            track_define(var_name, source_dir, record, stats)
                        )

                elif record.usage_type == "変数代入":
                    # スコープ判定して追跡（ホスト変数 or ローカル変数）
                    var_name = extract_variable_name_proc(record.code)
                    if not var_name:
                        # extract_host_var_name でも試みる
                        var_name = extract_host_var_name(record.code)
                    if var_name:
                        # filepath を解決
                        candidate = Path(record.filepath)
                        if not candidate.is_absolute():
                            candidate = source_dir / record.filepath
                        if candidate.exists():
                            all_records.extend(
                                track_variable(
                                    var_name, candidate,
                                    int(record.lineno), source_dir,
                                    record, stats,
                                )
                            )

            output_path = output_dir / f"{keyword}.tsv"
            write_tsv(all_records, output_path)

            processed_files.append(grep_path.name)
            direct_count = len(direct_records)
            indirect_count = len(all_records) - direct_count
            print(
                f"  {grep_path.name} → {output_path} "
                f"(直接: {direct_count} 件, 間接: {indirect_count} 件)"
            )

    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(2)

    print_report(stats, processed_files)


if __name__ == "__main__":
    main()
