# タスクリスト: ステップ2 間接参照・getter経由追跡実装

## フェーズ1: F-03 IndirectTracker（基本ユーティリティ）

- [x] T01: `determine_scope()` を実装（project/class/method の判定）
- [x] T02: `extract_variable_name()` を実装（コード行から変数名を抽出）
- [x] T03: `_resolve_java_file()` ヘルパーを実装（filepathのPath解決）
- [x] T04: `_get_method_scope()` 内部ヘルパーを実装（AST + ブレースカウンタ）

## フェーズ2: F-03 IndirectTracker（追跡関数）

- [x] T05: `track_constant()` を実装（static final をプロジェクト全体で追跡）
- [x] T06: `track_field()` を実装（フィールドを同一クラス内で追跡）
- [x] T07: `track_local()` を実装（ローカル変数を同一メソッド内で追跡）

## フェーズ3: F-04 GetterTracker

- [x] T08: `find_getter_names()` を実装（命名規則 + return文解析）
- [x] T09: `track_getter_calls()` を実装（getter呼び出しをプロジェクト全体で追跡）

## フェーズ4: main() 更新

- [x] T10: `main()` に第2・第3段階の処理ループを追加
- [x] T11: `all_records` に直接参照 + 間接参照 + getter参照を統合

## フェーズ5: 動作確認

- [x] T12: `python -m py_compile analyze.py` で構文確認
- [x] T13: `python -m flake8 analyze.py` でコードスタイル確認

---

## 実装後の振り返り

**実装完了日**: 2026-03-13

### 計画と実績の差分

- `find_getter_names()` の `ast_cache` 引数はグローバル `_ast_cache` で代替（ステップ1と統一）
- `track_constant()` / `track_field()` / `track_local()` に `source_dir` 引数を追加（スペックにないが `classify_usage()` 呼び出しに必要）
- `_search_in_lines()` ヘルパーを設計書にはない内部関数として追加し、追跡ロジックの重複を排除

### バリデーターで検出・修正した問題

1. `_ast_cache.get()` → `in` 演算子によるキー確認に変更（パースエラー済みファイルの再読み込みを防止）
2. `except Exception: pass` → stderrへの警告出力に変更（完全な握りつぶし防止）
3. `_VAR_NAME_PATTERN` 未使用定数を削除
4. `track_local` の `encoding_errors.append(origin.filepath)` → `str(java_file)` に統一（絶対パスで一貫性確保）

### 学んだこと

- `dict.get()` は値が `None` のエントリと未登録エントリを区別できないため、AST キャッシュには `in` 演算子チェックが必須
- `_search_in_lines()` のような内部ヘルパーを設けると、`track_constant` / `track_field` / `track_local` の重複を大幅に削減できる

### 次ステップへの申し送り

- ステップ3: F-06 Reporter（独立関数化）・test_analyze.py・run.sh・Makefile を実装する
- `_FIELD_DECL_PATTERN` のパッケージプライベートフィールド（修飾子なし）検出漏れは既知の制約として残っている。ステップ3のテスト実装時に検証・改善を検討すること
- `test_analyze.py` では `determine_scope`・`extract_variable_name`・`find_getter_names` のユニットテストを優先的に追加すること
