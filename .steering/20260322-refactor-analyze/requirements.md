# 要求内容: analyze.py リファクタリング

## 目的

`analyze.py` のコード品質を向上させる。機能変更は行わない。

## リファクタリング対象

1. **マジック文字列の排除**: `"project"/"class"/"method"` → `ScopeType` Enum
2. **未使用パラメータの削除**: `extract_variable_name()` の `usage_type` 引数
3. **キャッシュアクセスの統一**: `find_getter_names()` が `_ast_cache` を直接操作している → `get_ast()` を使う（`source_dir` 引数追加）
4. **エラー隠蔽の修正**: `determine_scope()` の `except: pass` → フォールバックファイルに記録
5. **関数抽出**: `main()` 内の間接追跡ロジック（30行超）を `_track_indirect_for_record()` に抽出

## 品質基準

- `python -m unittest discover` が全件パス
- `python -m flake8 analyze.py` が通る
- 型ヒントを適切に維持
