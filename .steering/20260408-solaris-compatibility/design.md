# 設計: Solaris 10 SPARC 対応

## アーキテクチャ方針

既存ファイルを変更せず、Solaris 専用ファイルを追加する。

```
grep_helper/
├── setup.sh            (既存・Linux向け・変更なし)
├── run.sh              (既存・Linux向け・変更なし)
├── setup_solaris.sh    (新規)
├── run_solaris.sh      (新規)
├── wheelhouse/
│   ├── .gitkeep        (新規)
│   └── README.txt      (新規)
└── Makefile            (既存ターゲット変更なし・新規ターゲット追記)
```

## setup_solaris.sh 設計

```
#!/bin/sh
set -e

1. wheelhouse/ ディレクトリの存在確認
2. Python を探す
   - PYTHON_CMD 環境変数が設定されていれば優先使用
   - 未設定の場合: python3.7, python3, python を順番に試す
   - 各コマンドを直接実行してバージョン確認（if条件内なのでset -eは発火しない）
3. python -m venv .venv
4. .venv/bin/pip が存在するか確認
5. .venv/bin/pip install --no-index --find-links=wheelhouse/ -r requirements.txt
```

### POSIX sh 互換の工夫

```sh
# command -v の代わり: if条件内で直接実行してエラーキャッチ
for cmd in python3.7 python3 python; do
    if "$cmd" -c "import sys; assert sys.version_info >= (3, 7)" 2>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done
```

`set -e` は `if` 条件内のコマンド失敗では発火しない（POSIX仕様）。
コマンドが存在しない場合も `if` 内なので安全。

## run_solaris.sh 設計

```sh
#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "エラー: setup_solaris.sh を先に実行してください。" >&2
    exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT_DIR/analyze.py" "$@"
```

`source .venv/bin/activate` を使わず `.venv/bin/python` を直接呼び出す。
venv 内の Python は自身の site-packages を参照するため activate 不要。

## wheelhouse 方針

- `javalang` は純粋Pythonパッケージ（C拡張なし）
- wheel ファイルは `py3-none-any` タグ → Linux/SPARC/Windows で共通
- Linux 開発環境で `pip download` して Solaris に持ち込む

## Makefile 追記

既存の `.PHONY` 行と既存ターゲットは変更なし。末尾に追記。

```makefile
.PHONY: download-wheels package-solaris

download-wheels:
    mkdir -p wheelhouse
    pip download -r requirements.txt -d wheelhouse
    @echo "..."

package-solaris: download-wheels
    mkdir -p dist
    zip -r dist/grep_analyzer_solaris.zip ...
```

## Python バージョン互換性

`analyze.py` は既に `from __future__ import annotations` を使用。
全型ヒントが文字列化されるため、Python 3.7.5 で実行時エラーなし。

検証済み互換性:
- `dataclasses` (Python 3.7+) ✓
- `list[str]` 型ヒント → PEP 563 で文字列化 ✓
- `str | None` 型ヒント → PEP 563 で文字列化 ✓
- ウォルラス演算子なし ✓
- `match` 文なし ✓
