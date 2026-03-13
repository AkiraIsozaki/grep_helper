# タスクリスト: 既知制約の全解消

## フェーズ1: 設計書作成

- [x] design.md 作成

## フェーズ2: テスト追加（カバレッジ向上）

- [x] T01: TestProcessGrepFile を追加（process_grep_file）
- [x] T02: TestGetAst を追加（get_ast・ASTキャッシュ）
- [x] T03: TestClassifyUsage を追加（classify_usage・_classify_by_ast）
- [x] T04: TestResolveJavaFile を追加（_resolve_java_file）
- [x] T05: TestGetMethodScope を追加（_get_method_scope）
- [x] T06: TestSearchInLines を追加（_search_in_lines）
- [x] T07: TestTrackConstant を追加（track_constant）
- [x] T08: TestTrackField を追加（track_field）
- [x] T09: TestTrackLocal を追加（track_local）
- [x] T10: TestFindGetterNames を追加（find_getter_names）
- [x] T11: TestTrackGetterCalls を追加（track_getter_calls）
- [x] T12: TestBuildParser を追加（build_parser）
- [x] TestMain を追加（main() のエンドツーエンドテスト）
- [x] TestGetAstExceptionHandling を追加（get_ast の例外処理）

## フェーズ3: 統合テストの厳密化

- [x] T13: assertGreaterEqual を特定行の存在確認チェックに変更

## フェーズ4: 動作確認

- [x] T14: `python -m coverage report --include=analyze.py` が 80% 以上（結果: 84%）
- [x] T15: `python -m unittest discover -v` が全テストパス（80テスト全パス）
- [x] T16: `python -m flake8 analyze.py test_analyze.py` が通る

---

## 実装後の振り返り

**実装完了日**: 2026-03-13

### 計画と実績の差分

- TestMain と TestGetAstExceptionHandling を計画外で追加（main() のカバレッジがゼロだったため）
- 合計 80 テスト（追加: 46 件）

### 既知の問題と対処

- `filepath` は `source_dir` 基準の相対パス（例: `"Constants.java"`）でないと `_resolve_java_file` / `get_ast` が解決できない。grep ファイルに記録されているプロジェクトルート基準のパスはフォールバック扱い（正規表現分類）になる。テストではこれを考慮して source_dir 基準の相対パスを使用した。
- 統合テストの期待 TSV は 6 列（src_var/src_file/src_lineno が空のため末尾省略）で、実際の出力は 9 列。`normalize()` ヘルパーで末尾空文字を除去して比較する方式で対応した。

### 最終テスト結果

- 80 テスト全パス
- カバレッジ: 84%（目標 80% 達成）
- flake8 / py_compile 全クリア
