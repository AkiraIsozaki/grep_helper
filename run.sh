#!/bin/bash
set -e
# grep結果自動分類ツール 実行スクリプト（Unix/Mac）
# 使い方: ./run.sh --source-dir /path/to/javaproject [--input-dir input] [--output-dir output]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "エラー: .venv が見つかりません。先に setup.sh を実行してください。" >&2
    exit 1
fi

source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/analyze.py" "$@"
