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

（実装完了後に記載）
