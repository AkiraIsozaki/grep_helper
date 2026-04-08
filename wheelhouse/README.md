# wheelhouse/ ディレクトリについて（Solaris 10 SPARC オフライン用）

このディレクトリは Solaris 10 SPARC のオフライン環境で依存パッケージを
インストールするための wheel ファイルを格納します。

---

## 格納ファイル

| ファイル | パッケージ | 説明 |
|---------|-----------|------|
| `javalang-0.13.0-py3-none-any.whl` | javalang 0.13.0 | Java AST 解析ライブラリ（本体） |
| `six-1.17.0-py2.py3-none-any.whl` | six 1.17.0 | javalang の依存パッケージ |

> どちらも **純粋 Python パッケージ**（C拡張なし）です。
> wheel タグが `none-any` のため、Linux で取得したファイルを Solaris 10 SPARC でもそのまま使用できます。

---

## wheel ファイルの再取得（インターネット接続環境で実行）

```sh
# make を使う場合
make download-wheels

# pip を直接使う場合
pip download -r requirements.txt -d wheelhouse
```

Linux / Mac の開発環境で実行してください。生成された `wheelhouse/` ごと Solaris に持ち込みます。

---

## Solaris 10 SPARC での使い方

wheel ファイルはリポジトリに含まれているため、追加作業は不要です。

```sh
# 1. Linux/Mac でリポジトリを clone してそのまま Solaris に転送

# 2. Python 3.7 をビルド（Sun Studio cc）
PYTHON_PREFIX=/opt/python37 sh build_python_solaris.sh

# 3. grep_helper をセットアップ
PYTHON_CMD=/opt/python37/bin/python3 sh setup_solaris.sh

# 4. 実行
sh run_solaris.sh --source-dir /path/to/javaproject
```

---

## pip が使えない場合の手動インストール

Python ビルドに `ensurepip` が含まれておらず、venv に pip が入らない場合:

1. 別環境で `get-pip.py` を取得して `wheelhouse/` に配置する
2. 以下を実行する:

```sh
.venv/bin/python wheelhouse/get-pip.py --no-index --find-links=wheelhouse
```

3. 再度 `sh setup_solaris.sh` を実行する
