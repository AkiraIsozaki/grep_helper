# 要求内容: ステップ3 仕上げ・テスト・配布

## 概要

ステップ1・2で実装した analyze.py に対して、仕上げ・品質担保・配布準備を行う。

## 対象コンポーネント

1. **F-06: Reporter** — `print_report()` を独立関数として実装し、`main()` のインラインコードを置換
2. **test_analyze.py** — ユニットテスト（TestGrepParser / TestUsageClassifier / TestTsvWriter）
3. **統合テスト用フィクスチャ** — `tests/fixtures/` に Java サンプルと grep 結果を配置
4. **run.sh / run.bat** — venv 有効化 + analyze.py 実行ラッパー
5. **setup.sh / setup.bat** — venv 作成 + requirements.txt インストール
6. **Makefile** — `make test` / `make package` ターゲット
7. **README.txt** — 利用者向け手順書（日本語）

## 完了基準

- `python -m unittest discover -v` が全テストパス
- `python -m py_compile analyze.py` が通る
- `python -m flake8 analyze.py test_analyze.py` が通る
