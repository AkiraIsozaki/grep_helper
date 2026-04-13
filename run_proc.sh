#!/bin/bash
set -e
# Pro*C grep結果自動分類ツール 実行スクリプト（Unix/Mac）
# 使い方: ./run_proc.sh --source-dir /path/to/proc_project [--input-dir input] [--output-dir output]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "エラー: .venv が見つかりません。先に setup.sh を実行してください。" >&2
    exit 1
fi

source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/analyze_proc.py" "$@"
