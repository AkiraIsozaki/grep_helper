# タスクリスト: ステップ3 仕上げ・テスト・配布

## フェーズ1: F-06 Reporter

- [x] T01: `print_report()` を analyze.py に実装
- [x] T02: `main()` のインラインレポートを `print_report()` 呼び出しに置換

## フェーズ2: ユニットテスト

- [x] T03: `test_analyze.py` を作成（TestGrepParser: 4ケース）
- [x] T04: TestUsageClassifier を追加（7種の使用タイプ）
- [x] T05: TestTsvWriter を追加（エンコード・ソート・ヘッダー）
- [x] T06: TestIndirectTracker を追加（determine_scope・extract_variable_name）

## フェーズ3: 統合テスト用フィクスチャ

- [x] T07: `tests/fixtures/java/Constants.java` を作成
- [x] T08: `tests/fixtures/input/SAMPLE.grep` を作成
- [x] T09: `tests/fixtures/expected/SAMPLE.tsv` を作成（期待出力）
- [x] T10: TestIntegration クラスを test_analyze.py に追加

## フェーズ4: 配布ファイル

- [x] T11: `run.sh` を作成（Unix/Mac 実行ラッパー）
- [x] T12: `run.bat` を作成（Windows 実行ラッパー）
- [x] T13: `setup.sh` を作成（venv セットアップ Unix/Mac）
- [x] T14: `setup.bat` を作成（venv セットアップ Windows）
- [x] T15: `Makefile` を作成（test / lint / package / clean）
- [x] T16: `README.txt` を作成（利用者向け手順書）

## フェーズ5: 動作確認

- [x] T17: `python -m unittest discover -v` で全テスト確認（30件 OK）
- [x] T18: `python -m flake8 analyze.py test_analyze.py` で確認（違反ゼロ）
- [x] T19: `python -m py_compile analyze.py test_analyze.py` で構文確認

---

## 実装後の振り返り

**実装完了日**: 2026-03-13

### 計画と実績の差分

- TestReporter は設計書に記載がなかったが、バリデーター指摘で追加（F-06実装後のスペック未更新を解消）
- フィクスチャに Entity.java / Service.java を追加（当初は Constants.java のみだった）
- `extract_variable_name()` の `usage_type` 引数が内部未使用 → `# noqa: ARG001` で Pylance 警告を解消
- run.sh / setup.sh に `set -e` を追加（pip install 失敗時のエラー伝播保証）

### バリデーターで検出・修正した問題

1. `TestReporter` クラスが未実装 → 4ケース追加
2. `test_extract_variable_name_invalid_returns_none` の `assertIsInstance` → `assertIsNone` に修正
3. フィクスチャが Constants.java のみ → Entity.java / Service.java を追加
4. run.sh / setup.sh にエラー伝播がない → `set -e` 追加

### 最終テスト結果

- 34テスト全パス（TestGrepParser: 6、TestUsageClassifier: 10、TestTsvWriter: 6、TestIndirectTracker: 7、TestReporter: 4、TestIntegration: 1）
- flake8 / py_compile 全クリア

### 既知の制約（次バージョン以降）

- カバレッジ約35%（目標80%）。track_constant / track_field / track_local / track_getter_calls のユニットテストが未実装。統合テストで補完しているが定量目標には届いていない
- 統合テストの行一致チェックが `>=` による緩い比較（Entity.java/Service.java 追加後に完全一致比較へ格上げ推奨）
- `_FIELD_DECL_PATTERN` のパッケージプライベートフィールド検出漏れは既知制約として残存
