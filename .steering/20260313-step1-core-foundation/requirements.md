# 要求内容: ステップ1 コア基盤実装

## 概要

`analyze.py` の骨格となるコアコンポーネントを実装する。
このステップで「直接参照のみのTSV出力」まで動作する状態を目指す。

## 対象コンポーネント

1. **データモデル**: `GrepRecord`, `ProcessStats`, `RefType`, `UsageType`
2. **F-01: GrepParser**: `parse_grep_line()`, `process_grep_file()`
3. **F-02: UsageClassifier**: `classify_usage()`, `classify_usage_regex()`
4. **F-05: TsvWriter**: `write_tsv()`
5. **CLIエントリポイント**: `main()` + `build_parser()` + `_ast_cache`（ASTキャッシュ）

## スコープ外（次ステップ以降）

- F-03: IndirectTracker（間接参照追跡）
- F-04: GetterTracker（getter経由追跡）
- F-06: Reporter（処理レポート）
- テスト（test_analyze.py）
- run.sh / setup.sh / Makefile

## 完了基準

- `python -m py_compile analyze.py` が通る（構文エラーなし）
- `python analyze.py --source-dir /tmp --input-dir /tmp` が動作確認できる（入力なしでもクラッシュしない）
- 直接参照レコードがTSVに正しく出力されること
