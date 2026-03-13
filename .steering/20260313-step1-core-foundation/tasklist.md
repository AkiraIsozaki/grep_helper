# タスクリスト: ステップ1 コア基盤実装

## フェーズ1: データモデルと定数定義

- [x] T01: `RefType` Enum を実装（直接/間接/間接（getter経由））
- [x] T02: `UsageType` Enum を実装（7種）
- [x] T03: `GrepRecord` dataclass を実装（frozen=True）
- [x] T04: `ProcessStats` dataclass を実装
- [x] T05: `USAGE_PATTERNS` 定数をモジュールレベルで定義（プリコンパイル済み正規表現）

## フェーズ2: F-01 GrepParser

- [x] T06: `parse_grep_line()` を実装（Windowsパス対応・バイナリ通知行スキップ）
- [x] T07: `process_grep_file()` を実装（grepファイル全行処理・stats更新）

## フェーズ3: F-02 UsageClassifier

- [x] T08: `classify_usage_regex()` を実装（正規表現フォールバック）
- [x] T09: `get_ast()` ヘルパー関数を実装（ASTキャッシュ管理）
- [x] T10: `classify_usage()` を実装（AST解析 + 正規表現フォールバック）

## フェーズ4: F-05 TsvWriter

- [x] T11: `write_tsv()` を実装（UTF-8 BOM付き・ソート付き・output/自動作成）

## フェーズ5: CLIエントリポイント

- [x] T12: `build_parser()` を実装（argparse定義）
- [x] T13: `main()` を実装（入力検証・処理ループ・エラーハンドリング）
- [x] T14: `if __name__ == "__main__": main()` を追加

## フェーズ6: 補助ファイル

- [x] T15: `requirements.txt` を作成（javalang>=0.13.0,<1.0.0）
- [x] T16: `input/.gitkeep` と `output/.gitkeep` を作成
- [x] T17: `.gitignore` を作成
- [x] T18: `.flake8` を作成（max-line-length=120）

## フェーズ7: 動作確認

- [x] T19: `python -m py_compile analyze.py` で構文確認
- [x] T20: `python -m flake8 analyze.py` でコードスタイル確認

---

## 実装後の振り返り

**実装完了日**: 2026-03-13

### 計画と実績の差分

- `process_grep_file()` のシグネチャに `source_dir` を追加（スペックには含まれていなかったが、内部で `classify_usage` を呼ぶ設計上必要と判断）。機能設計書と乖離しているが次ステップで整合を確認する。
- `classify_usage()` の `ast_cache` 引数をグローバル変数 `_ast_cache` で代替。テストしやすさより実装シンプルさを優先した。
- F-06 Reporter は `main()` 内に簡易実装として内包（次ステップで独立関数化）。

### バリデーターで検出・修正した問題

1. `_GREP_LINE_PATTERN` が定義のみで未使用 → `re.split()` インライン呼び出しを `_GREP_LINE_PATTERN.split()` に修正
2. `except Exception: pass` → `stats.fallback_files` 記録付きに修正
3. `for path, node in tree:` の `path` が未使用 → `_` に変更

### 学んだこと

- flake8 の E221（複数スペースによる整列）は Enum や dataclass の定義で発生しやすい。整列は使わずスペース1つで統一すること。
- `re.Pattern.split()` は `re.split(pattern_str, ...)` と同等だが、プリコンパイル済みパターンを使うことでコードの意図が明確になる。

### 次ステップへの申し送り

- ステップ2: F-03 IndirectTracker・F-04 GetterTracker を実装する
- `classify_usage` の `ast_cache` 引数化はステップ2実装前に検討すること（F-03・F-04 が `ast_cache` を引数で受け取る設計のため）
- `process_grep_file` のシグネチャ乖離は機能設計書の更新で解決することが望ましい
