#!/bin/bash
set -e
# grep結果自動分類ツール セットアップスクリプト（Unix/Mac）
# Python 3.12以上が必要です。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "セットアップを開始します..."

# Python バージョン確認
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        VERSION=$("$cmd" -c "import sys; print(sys.version_info >= (3, 12))" 2>/dev/null)
        if [ "$VERSION" = "True" ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "エラー: Python 3.12以上が見つかりません。インストールしてください。" >&2
    exit 1
fi

echo "Python: $($PYTHON_CMD --version)"

# venv 作成
"$PYTHON_CMD" -m venv "$SCRIPT_DIR/.venv"
source "$SCRIPT_DIR/.venv/bin/activate"

# 依存ライブラリのインストール
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo "セットアップ完了。"
echo "実行方法: ./run.sh --source-dir /path/to/javaproject"
