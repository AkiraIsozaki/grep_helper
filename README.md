# grep結果自動分類ツール - 利用者向け手順書

Java プロジェクトに対して grep した結果ファイルを読み込み、
使用タイプ（定数定義・条件判定・変数代入など）を自動分類して
Excel で開ける TSV ファイルに出力します。

---

## 前提条件

| 項目 | Linux / Mac | Solaris 10 SPARC |
|------|-------------|-----------------|
| Python | 3.12 以上 | 3.7 以上（別途持ち込み） |
| OS | Windows / Mac / Linux | Solaris 10 1/13 SPARC |

> **Solaris 10 について**: ホスト OS に Python 3 が含まれないため、
> 別途 Python 3.7 以上を持ち込む必要があります。
> 詳細は [Solaris 10 SPARC 向け手順](#solaris-10-sparc-向けセットアップオフライン環境) を参照してください。

---

## セットアップ手順（Linux / Mac）

```sh
chmod +x setup.sh run.sh
./setup.sh
```

### Windows の場合

```bat
setup.bat
```

セットアップ完了後、`.venv/` ディレクトリが作成されます。

---

## 基本的な使い方

### 1. grep 結果ファイルを `input/` に配置する

```sh
# Unix/Mac
grep -rn "ERROR_CODE" /path/to/javaproject > input/ERROR_CODE.grep
```

```powershell
# Windows PowerShell
grep -rn "ERROR_CODE" C:\path\to\javaproject > input\ERROR_CODE.grep
```

> ファイル名（拡張子なし）が「検索文言」として出力 TSV に記録されます。
> 複数ファイルを同時に配置して一括処理することもできます。

### 2. ツールを実行する

```sh
# Unix/Mac
./run.sh --source-dir /path/to/javaproject

# Windows
run.bat --source-dir C:\path\to\javaproject
```

### 3. `output/` に TSV ファイルが生成される

```
input/ERROR_CODE.grep  →  output/ERROR_CODE.tsv
```

---

## CLI オプション一覧

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--source-dir` | （必須） | Java ソースコードのルートディレクトリ |
| `--input-dir` | `input/` | grep 結果ファイルの配置ディレクトリ |
| `--output-dir` | `output/` | TSV 出力先ディレクトリ |

```sh
./run.sh --source-dir /path/to/java \
         --input-dir /custom/input \
         --output-dir /custom/output
```

---

## 出力 TSV の列定義

| 列名 | 説明 |
|------|------|
| 文言 | grep したキーワード（入力ファイル名から取得） |
| 参照種別 | 直接 / 間接 / 間接（getter経由） |
| 使用タイプ | アノテーション / 定数定義 / 変数代入 / 条件判定 / return文 / メソッド引数 / その他 |
| ファイルパス | 該当行の Java ファイルパス |
| 行番号 | 該当行の行番号 |
| コード行 | 該当行のコード（前後の空白を除去済み） |
| 参照元変数名 | 間接参照の場合：経由した変数/定数名 |
| 参照元ファイル | 間接参照の場合：変数/定数が定義されたファイルパス |
| 参照元行番号 | 間接参照の場合：変数/定数が定義された行番号 |

---

## Solaris 10 SPARC 向けセットアップ（オフライン環境）

### 前提条件

| 項目 | 内容 |
|------|------|
| OS | Solaris 10 1/13 SPARC |
| C コンパイラ | Sun Studio `cc`（gcc 不要） |
| GNU make | `/usr/sfw/bin/gmake` など（SFW パッケージ） |
| ネットワーク | オフライン（持ち込み一式で完結） |

> **Python 2.6.4 について**: Solaris 10 標準の Python 2.6.4 は使用できません。
> 以下の手順で Python 3.7 をソースからビルドします。

---

### 手順1: インターネット接続環境（Linux/Mac）でリポジトリを取得

```sh
git clone <repository-url> grep_helper
```

リポジトリには以下が**すべて含まれています**（追加作業不要）：

| ファイル | 説明 |
|---------|------|
| `python-src/Python-3.7.17.tgz` | Python 3.7.17 ソース（GitHub アーカイブ） |
| `build_python_solaris.sh` | Python ビルドスクリプト（`cc` 対応） |
| `wheelhouse/*.whl` | javalang / six（純粋 Python wheel） |
| `setup_solaris.sh` | grep_helper セットアップスクリプト |
| `run_solaris.sh` | 実行スクリプト |

---

### 手順2: Solaris 10 に転送

`grep_helper/` ディレクトリごと Solaris 10 に転送します（scp / USB メモリ など）。

---

### 手順3: Python 3.7 をビルド（初回のみ）

```sh
sh build_python_solaris.sh
```

Python 3.7 はツールディレクトリ内の `python37/` にインストールされます（root 不要）。

> **ビルド時間**: SPARC の性能によりますが、数十分かかる場合があります。  
> **C コンパイラ**: Sun Studio `cc` を使用します（gcc 3.4.3 は古すぎるため非推奨）。  
> **GNU make**: `/usr/sfw/bin/gmake` が必要です（Solaris 10 SFW パッケージ `SUNWgmake`）。  
> **Sun Studio `cc`**: PATH に含まれている必要があります（例: `/opt/SUNWspro/bin`）。

---

### 手順4: grep_helper のセットアップ

```sh
sh setup_solaris.sh
```

`python37/` が存在すれば自動的に検出されます。

---

### 手順5: 実行

```sh
sh run_solaris.sh --source-dir /path/to/javaproject
```

---

## よくあるエラーと対処方法

### `--source-dir` で指定したディレクトリが存在しません

`--source-dir` で指定したパスが正しいか確認してください。

### `input/` ディレクトリに grep 結果ファイルがありません

`input/` に `.grep` 拡張子のファイルが存在するか確認してください。

### `.venv` が見つかりません

`setup.sh`（または `setup.bat` / `setup_solaris.sh`）を先に実行してください。

### `wheelhouse/` に `.whl` ファイルが見つかりません（Solaris のみ）

インターネット接続環境で `make download-wheels` を実行してください。

### 仮想環境に pip が含まれていません（Solaris のみ）

Python ビルドに `ensurepip` が含まれていない場合に発生します。
`wheelhouse/README.md` の手動インストール手順を参照してください。

### 処理が遅い場合

Java ソースファイルが大量にある場合は時間がかかります。
AST キャッシュにより 2 回目以降の同一ファイル解析は高速化されます。

---

## ライセンス・問い合わせ

社内ツールのため再配布不可。問い合わせは開発担当者までご連絡ください。
