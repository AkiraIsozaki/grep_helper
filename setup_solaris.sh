#!/bin/sh
# grep結果自動分類ツール セットアップスクリプト（Solaris 10 SPARC / オフライン専用）
#
# 前提条件:
#   - Python 3.7 以上が利用可能であること（ホストOSに無い場合は別途持ち込む）
#   - wheelhouse/ ディレクトリに .whl ファイルが存在すること
#     （インターネット接続環境で "make download-wheels" を実行して取得）
#
# 使い方:
#   ./setup_solaris.sh
#
# Pythonのパスを明示する場合:
#   PYTHON_CMD=/opt/python37/bin/python3.7 ./setup_solaris.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WHEELHOUSE="$SCRIPT_DIR/wheelhouse"

echo "セットアップを開始します（Solaris 10 SPARC / オフライン）..."
echo ""

# ----------------------------------------------------------------
# 1. wheelhouse ディレクトリの確認
# ----------------------------------------------------------------
if [ ! -d "$WHEELHOUSE" ]; then
    echo "エラー: wheelhouse/ ディレクトリが見つかりません。" >&2
    echo "" >&2
    echo "  インターネット接続環境（Linux/Mac）で以下を実行してから" >&2
    echo "  wheelhouse/ ディレクトリごと持ち込んでください:" >&2
    echo "    make download-wheels" >&2
    exit 1
fi

# .whl ファイルの存在確認（ls の終了コードで判定）
if ! ls "$WHEELHOUSE"/*.whl > /dev/null 2>&1; then
    echo "エラー: wheelhouse/ に .whl ファイルが見つかりません。" >&2
    echo "" >&2
    echo "  インターネット接続環境（Linux/Mac）で以下を実行してください:" >&2
    echo "    make download-wheels" >&2
    exit 1
fi

echo "wheelhouse/ を確認しました。"

# ----------------------------------------------------------------
# 2. Python 3.7 以上を探す
#    PYTHON_CMD 環境変数が設定されていればそれを優先使用。
#    set -e のもとで if 条件内のコマンド失敗は終了を発火しない（POSIX仕様）。
# ----------------------------------------------------------------
if [ -n "${PYTHON_CMD:-}" ]; then
    # ユーザー指定のパスを検証
    if ! "$PYTHON_CMD" -c "import sys; assert sys.version_info >= (3, 7)" 2>/dev/null; then
        echo "エラー: PYTHON_CMD=$PYTHON_CMD は Python 3.7 以上ではありません。" >&2
        exit 1
    fi
else
    PYTHON_CMD=""
    for cmd in python3.7 python3.8 python3.9 python3.10 python3.11 python3 python; do
        if "$cmd" -c "import sys; assert sys.version_info >= (3, 7)" 2>/dev/null; then
            PYTHON_CMD="$cmd"
            break
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        echo "エラー: Python 3.7 以上が見つかりません。" >&2
        echo "" >&2
        echo "  Python 3 をインストールするか、以下のように実行してください:" >&2
        echo "    PYTHON_CMD=/path/to/python3 ./setup_solaris.sh" >&2
        exit 1
    fi
fi

echo "Python: $("$PYTHON_CMD" --version 2>&1)"

# ----------------------------------------------------------------
# 3. 仮想環境（venv）の作成
# ----------------------------------------------------------------
echo "仮想環境を作成しています..."
"$PYTHON_CMD" -m venv "$SCRIPT_DIR/.venv"

VENV_PIP="$SCRIPT_DIR/.venv/bin/pip"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# ----------------------------------------------------------------
# 4. pip の存在確認
#    Python ビルドによっては ensurepip が含まれない場合がある。
# ----------------------------------------------------------------
if [ ! -f "$VENV_PIP" ]; then
    echo "エラー: 仮想環境に pip が含まれていません。" >&2
    echo "" >&2
    echo "  Python ビルドに ensurepip モジュールが含まれているか確認してください。" >&2
    echo "  または、以下の手順で pip を手動インストールしてください:" >&2
    echo "    1. wheelhouse/ に get-pip.py を配置する" >&2
    echo "       (https://bootstrap.pypa.io/get-pip.py を別環境で取得)" >&2
    echo "    2. $VENV_PYTHON wheelhouse/get-pip.py --no-index \\" >&2
    echo "           --find-links=$WHEELHOUSE" >&2
    echo "    3. 再度 ./setup_solaris.sh を実行する" >&2
    exit 1
fi

# ----------------------------------------------------------------
# 5. 依存ライブラリをオフラインインストール
# ----------------------------------------------------------------
echo "依存ライブラリをインストールしています（wheelhouse から）..."
"$VENV_PIP" install \
    --no-index \
    --find-links="$WHEELHOUSE" \
    -r "$SCRIPT_DIR/requirements.txt" \
    --quiet

echo ""
echo "セットアップ完了。"
echo "実行方法: ./run_solaris.sh --source-dir /path/to/javaproject"
