# 要求内容: Solaris 10 SPARC 対応

## 背景

grep_helper を Solaris 10 1/13 (s10s_u11wos_24a SPARC) 環境で動作させたい。

## 制約条件

| 項目 | 内容 |
|------|------|
| ターゲットOS | Solaris 10 1/13 SPARC |
| Python 3 | ホストOSに未インストール → 利用者が別途持ち込む |
| ネットワーク | オフライン環境 → pip install 不可 |
| 依存パッケージ調達 | wheelhouse 方式（事前ダウンロード済み whl ファイル） |

## 既存Linux環境への影響

- **ゼロ影響** を原則とする
- 既存の `setup.sh` / `run.sh` / `Makefile` のターゲットは一切変更しない

## 必要な成果物

1. `setup_solaris.sh` — Solaris 10 SPARC 向けセットアップスクリプト
   - POSIX sh 互換（`#!/bin/sh`、`source` 不使用）
   - Python 3.7+ チェック（`PYTHON_CMD` 環境変数でパス上書き可能）
   - wheelhouse/ からオフラインインストール

2. `run_solaris.sh` — Solaris 10 SPARC 向け実行スクリプト
   - POSIX sh 互換
   - `.venv/bin/python` を直接呼び出し（activate 不使用）

3. `wheelhouse/` — whl ファイル格納ディレクトリ（.gitkeep + README）

4. `Makefile` 追記 — `download-wheels` / `package-solaris` ターゲット追加

5. `README.txt` 追記 — Solaris 10 向けセクション追加

## Solaris 10 固有の技術的制約

- `/bin/sh` は旧 Bourne shell（bash でない）
  - `source` 不可 → `.` (ドット) コマンドも使わない
  - `command -v` 不安定 → コマンド存在確認はコマンド直接実行でエラーキャッチ
- venv activate を使わず `.venv/bin/python` を直接呼び出す
- `javalang` は純粋Pythonパッケージ → Linux で取得した whl が SPARC でも使用可能
