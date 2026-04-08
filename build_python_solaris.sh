#!/bin/sh
# Python 3.7 ビルドスクリプト（Solaris 10 SPARC / Sun Studio cc 専用）
#
# 前提条件:
#   - python-src/Python-3.7.17.tgz が存在すること
#     （インターネット接続環境で "make download-python-src" を実行して取得）
#   - Sun Studio の cc が PATH に含まれること
#     （例: /opt/SUNWspro/bin を PATH に追加）
#   - GNU make が利用可能なこと
#     （Solaris 10 SFW パッケージの /usr/sfw/bin/gmake など）
#
# 使い方:
#   sh build_python_solaris.sh
#
# インストール先を変更する場合（デフォルト: /opt/python37）:
#   PYTHON_PREFIX=/home/yourname/python37 sh build_python_solaris.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON_VERSION="3.7.17"
PYTHON_ARCHIVE="$SCRIPT_DIR/python-src/Python-${PYTHON_VERSION}.tgz"
# GitHub アーカイブは cpython-X.Y.Z/ として展開される
PYTHON_SRC_DIR="cpython-${PYTHON_VERSION}"
# ツールディレクトリ内にインストール（root不要・共有サーバ対応）
PYTHON_PREFIX="${PYTHON_PREFIX:-$SCRIPT_DIR/python37}"
BUILD_DIR="$SCRIPT_DIR/python-build"

echo "Python ${PYTHON_VERSION} ビルドを開始します（Solaris 10 SPARC / cc）..."
echo "インストール先: $PYTHON_PREFIX"
echo ""

# ----------------------------------------------------------------
# 1. ソースアーカイブの確認
# ----------------------------------------------------------------
if [ ! -f "$PYTHON_ARCHIVE" ]; then
    echo "エラー: $PYTHON_ARCHIVE が見つかりません。" >&2
    echo "" >&2
    echo "  インターネット接続環境（Linux/Mac）で以下を実行してください:" >&2
    echo "    make download-python-src" >&2
    echo "" >&2
    echo "  その後、python-src/ ディレクトリごと Solaris に持ち込んでください。" >&2
    exit 1
fi

# ----------------------------------------------------------------
# 2. GNU make を探す
#    Python 3.7 のビルドシステムは GNU make が必要
# ----------------------------------------------------------------
GMAKE=""
for cmd in gmake /usr/sfw/bin/gmake /usr/gnu/bin/make /opt/csw/bin/gmake /usr/local/bin/gmake; do
    if "$cmd" --version 2>/dev/null | grep -q "GNU Make"; then
        GMAKE="$cmd"
        break
    fi
done

if [ -z "$GMAKE" ]; then
    echo "エラー: GNU make が見つかりません。" >&2
    echo "" >&2
    echo "  Solaris 10 SFW パッケージ (SUNWgmake) をインストールするか、" >&2
    echo "  以下のパスを確認してください:" >&2
    echo "    /usr/sfw/bin/gmake" >&2
    exit 1
fi
echo "GNU make : $GMAKE"

# ----------------------------------------------------------------
# 3. cc の確認
# ----------------------------------------------------------------
if ! cc -V 2>/dev/null; then
    echo "エラー: cc が見つかりません。" >&2
    echo "  Sun Studio の bin ディレクトリ（例: /opt/SUNWspro/bin）を PATH に追加してください。" >&2
    exit 1
fi
echo ""

# ----------------------------------------------------------------
# 4. ソース展開
# ----------------------------------------------------------------
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
echo "ソースを展開しています..."
tar xzf "$PYTHON_ARCHIVE" -C "$BUILD_DIR"
cd "$BUILD_DIR/${PYTHON_SRC_DIR}"

# ----------------------------------------------------------------
# 5. configure
#    -xO2  : 最適化レベル2（Sun Studio構文）
#    --disable-shared : 共有ライブラリ不要の静的リンク
#                       libpython3.7.so への依存がなくなり可搬性が向上
#    --with-ensurepip=install : pip を同梱
# ----------------------------------------------------------------
echo "configure を実行しています..."
CC=cc \
CFLAGS="-xO2" \
./configure \
    --prefix="$PYTHON_PREFIX" \
    --disable-shared \
    --with-ensurepip=install

# ----------------------------------------------------------------
# 6. ビルド
# ----------------------------------------------------------------
echo ""
echo "ビルドしています（数十分かかる場合があります）..."
"$GMAKE" -j2

# ----------------------------------------------------------------
# 7. インストール
# ----------------------------------------------------------------
echo ""
echo "インストールしています..."
"$GMAKE" install

echo ""
echo "================================================================"
echo "Python ${PYTHON_VERSION} のインストールが完了しました。"
echo "インストール先: $PYTHON_PREFIX"
echo "================================================================"
echo ""
echo "次のステップ（grep_helper のセットアップ）:"
echo "  sh $SCRIPT_DIR/setup_solaris.sh"
