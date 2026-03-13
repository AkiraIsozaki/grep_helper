# 要求内容: 既知制約の全解消

## 解消対象

1. **テストカバレッジ 34% → 80%以上**
   - 未テスト: process_grep_file, get_ast, classify_usage, _resolve_java_file,
     _get_method_scope, _search_in_lines, track_constant, track_field, track_local,
     find_getter_names, track_getter_calls, build_parser

2. **統合テストの行一致チェックが `>=` による緩い比較**
   - 直接参照の特定行が出力に含まれることを確認するチェックに格上げ

3. ~~パッケージプライベートフィールドの検出漏れ~~ → **前のステップで解消済み**

## 完了基準

- `python -m coverage report --include=analyze.py` が 80%以上
- `python -m unittest discover -v` が全テストパス
- `python -m flake8 analyze.py test_analyze.py` が通る
