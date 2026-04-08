#!/bin/sh
# grep結果自動分類ツール 実行スクリプト（Solaris 10 SPARC）
#
# 使い方:
#   ./run_solaris.sh --source-dir /path/to/javaproject [--input-dir input] [--output-dir output]
#
# 注意:
#   事前に ./setup_solaris.sh を実行して仮想環境を作成してください。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "エラー: .venv が見つかりません。先に ./setup_solaris.sh を実行してください。" >&2
    exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT_DIR/analyze.py" "$@"
