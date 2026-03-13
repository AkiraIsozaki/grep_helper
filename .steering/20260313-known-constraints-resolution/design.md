# 設計: 既知制約の全解消

## 解消方針

### 1. テストカバレッジ 34% → 80%

未テスト関数を対象に新テストクラスを追加する。

| テストクラス | 対象関数 |
|---|---|
| TestProcessGrepFile | process_grep_file |
| TestGetAst | get_ast |
| TestClassifyUsage | classify_usage, _classify_by_ast |
| TestResolveJavaFile | _resolve_java_file |
| TestGetMethodScope | _get_method_scope |
| TestSearchInLines | _search_in_lines |
| TestTrackConstant | track_constant |
| TestTrackField | track_field |
| TestTrackLocal | track_local |
| TestFindGetterNames | find_getter_names |
| TestTrackGetterCalls | track_getter_calls |
| TestBuildParser | build_parser |

### 2. 統合テストの厳密化

`assertGreaterEqual` を廃止し、期待する直接参照行が出力に含まれることをアサートする。
Constants.java の直接参照（isValid メソッド内）が SAMPLE.tsv に出力されることを検証。

## フィクスチャ利用方針

- `tests/fixtures/java/` にある Constants.java / Entity.java / Service.java を最大限活用
- 必要に応じて `tempfile` で一時ファイルを作成
- `_ast_cache` を各テストでリセット（テスト間の干渉を防ぐ）
