# タスクリスト

## 🚨 タスク完全完了の原則

**このファイルの全タスクが完了するまで作業を継続すること**

### 必須ルール
- **全てのタスクを`[x]`にすること**
- 「時間の都合により別タスクとして実施予定」は禁止
- 「実装が複雑すぎるため後回し」は禁止
- 未完了タスク（`[ ]`）を残したまま作業を終了しない

---

## フェーズ1: データモデル・共通基盤

- [x] データモデルと定数を定義する
  - [x] `GrepRecord`（NamedTuple） — Javaツールと同一構造
  - [x] `ProcessStats`（dataclass） — Javaツールと同一構造
  - [x] `RefType` Enum（直接 / 間接） — Pro*CはGetterなし
  - [x] `ProcUsageType` Enum（7種: EXEC SQL文 / #define定数定義 / 条件判定 / return文 / 変数代入 / 関数引数 / その他）
  - [x] `PROC_USAGE_PATTERNS`（プリコンパイル正規表現リスト）
  - [x] `_BINARY_PATTERN`（バイナリ通知行検出）
  - [x] `_file_cache`（ファイル行キャッシュ、上限800エントリ）

## フェーズ2: GrepParser

- [x] `parse_grep_line(line: str) -> dict | None` を実装する
  - [x] `filepath:lineno:code` 形式をパース（Windowsパス対応）
  - [x] バイナリ通知行・空行・不正行は `None` を返す

- [x] `_read_source_file(path: Path, stats: ProcessStats) -> list[str]` を実装する
  - [x] `encoding='shift_jis', errors='replace'` で読み込む
  - [x] `_file_cache` を参照・更新する（上限超過時は古いエントリを削除）

- [x] `process_grep_file(path: Path, keyword: str, source_dir: Path, stats: ProcessStats) -> list[GrepRecord]` を実装する
  - [x] `encoding='cp932', errors='replace'` でgrepファイルを読み込む
  - [x] 各行を `parse_grep_line()` でパース
  - [x] パース成功行を `GrepRecord`（usage_type未設定）として収集
  - [x] `stats` を更新する

## フェーズ3: ProcUsageClassifier

- [x] `classify_usage_proc(code: str) -> str` を実装する
  - [x] `PROC_USAGE_PATTERNS` を優先度順に評価する
  - [x] 非マッチは「その他」を返す

## フェーズ4: ProcIndirectTracker

- [x] `extract_define_name(code: str) -> str | None` を実装する
  - [x] `#define NAME value` から NAME を抽出する
  - [x] マッチしない場合は `None` を返す

- [x] `extract_variable_name_proc(code: str) -> str | None` を実装する
  - [x] C変数宣言行（`type varName = ...` / `type varName[N] = ...`）から変数名を抽出する

- [x] `extract_host_var_name(code: str) -> str | None` を実装する
  - [x] DECLARE SECTION内の変数宣言行から変数名を抽出する（`char varName[N];` など）

- [x] `_find_function_scope(lines: list[str], lineno: int) -> tuple[int, int]` を実装する
  - [x] 指定行番号から上方向に関数の `{` を探す
  - [x] `{` `}` のネスト深度を追跡して関数の終端行を返す
  - [x] `(start_lineno, end_lineno)` のタプルを返す

- [x] `track_define(var_name: str, source_dir: Path, origin: GrepRecord, stats: ProcessStats) -> list[GrepRecord]` を実装する
  - [x] `source_dir` 配下の `.pc` / `.h` ファイルを全件スキャンする
  - [x] `var_name` を含む行を収集し、`classify_usage_proc()` で分類する
  - [x] `_file_cache` を利用する
  - [x] 定義行自体は重複追加しない（`origin.filepath:origin.lineno` と一致する行はスキップ）

- [x] `_detect_host_var_scope(lines: list[str]) -> list[tuple[int, int]]` を実装する
  - [x] ファイル全体をスキャンして DECLARE SECTION の範囲（開始行・終了行のリスト）を返す

- [x] `track_variable(var_name: str, filepath: Path, lineno: int, source_dir: Path, origin: GrepRecord, stats: ProcessStats) -> list[GrepRecord]` を実装する
  - [x] スコープ判定: DECLARE SECTIONの内部 → ホスト変数（同一ファイル全体）、それ以外 → ローカル変数（同一関数スコープ）
  - [x] ホスト変数の場合は `:var_name` パターンで同一ファイルを検索する
  - [x] ローカル変数の場合は `_find_function_scope()` でスコープを特定し、スコープ内を検索する

## フェーズ5: TsvWriter・Reporter

- [x] `write_tsv(records: list[GrepRecord], output_path: Path) -> None` を実装する
  - [x] UTF-8 BOM付き (`encoding='utf-8-sig'`)
  - [x] ヘッダ行: 文言 / 参照種別 / 使用タイプ / ファイルパス / 行番号 / コード行 / 参照元変数名 / 参照元ファイル / 参照元行番号
  - [x] ソート: `(keyword, filepath, int(lineno))`

- [x] `print_report(stats: ProcessStats, processed_files: list[str]) -> None` を実装する
  - [x] 処理ファイル一覧・総行数・有効行数・スキップ行数を出力する
  - [x] エンコーディングエラーのファイル一覧を出力する（あれば）

## フェーズ6: CLI・エントリポイント

- [x] `build_parser() -> argparse.ArgumentParser` を実装する
  - [x] `--source-dir`（必須）
  - [x] `--input-dir`（デフォルト `input/`）
  - [x] `--output-dir`（デフォルト `output/`）

- [x] `main()` を実装する
  - [x] 引数バリデーション（`--source-dir` の存在確認など）
  - [x] `input/*.grep` を全件検出
  - [x] 各ファイルに対して分析パイプラインを実行
  - [x] `write_tsv()` で出力
  - [x] `print_report()` でサマリ表示

- [x] `if __name__ == '__main__': main()` を追加する

## フェーズ7: 実行スクリプト

- [x] `run_proc.sh` を作成する（`run.sh` と同一構造）
- [x] `run_proc.bat` を作成する（`run.bat` と同一構造）

## フェーズ8: ユニットテスト

- [x] `test_analyze_proc.py` を作成する
  - [x] `TestParseGrepLine`: 正常行・バイナリ通知行・空行・不正フォーマット行
  - [x] `TestClassifyUsageProc`: 7種の使用タイプのサンプルコード
  - [x] `TestExtractDefineName`: `#define NAME "value"` からNAMEを抽出
  - [x] `TestExtractVariableNameProc`: 各種変数宣言パターン
  - [x] `TestWriteTsv`: 列数・エンコード・ソート順

## フェーズ9: 統合テスト用フィクスチャと統合テスト

- [x] `tests/proc/src/constants.h` を作成する
  - [x] `#define SAMPLE_CODE "TARGET"` を含む
- [x] `tests/proc/src/sample.pc` を作成する
  - [x] 直接参照・#define間接参照・ホスト変数間接参照を含む
- [x] `tests/proc/input/TARGET.grep` を作成する
  - [x] `sample.pc` と `constants.h` の該当行を含むgrep結果
- [x] `tests/proc/expected/TARGET.tsv` を作成する
  - [x] 期待TSV（UTF-8 BOM付き）
- [x] `test_analyze_proc.py` に統合テストクラス `TestE2EProc` を追加する
  - [x] ツールを実行して出力TSVと期待TSVを比較する

## フェーズ10: 品質チェック

- [x] すべてのテストが通ることを確認する
  - [x] `python -m unittest test_analyze_proc.py` → 31件 OK
- [x] 構文エラーがないことを確認する
  - [x] `python -m py_compile analyze_proc.py` → OK

---

## 実装後の振り返り

### 実装完了日
2026-04-13

### 計画と実績の差分

**計画と異なった点**:
- `PROC_USAGE_PATTERNS` の変数代入パターンを設計書の `r'\b\w[\w\s\*\[\]]*\s+\w+\s*[=;]'` から `r'\b\w[\w\*]*\s+\*?\w+\s*(?:\[.*?\])?\s*[=;]'` に変更。設計書のパターンは `[\w\s\*\[\]]*` にスペースが含まれており `char localCode[] = ...` にマッチしなかった。
- `extract_variable_name_proc()` に `_C_TYPE_PATTERN` による事前フィルタと EXEC SQL 行の除外チェックを追加。単純なトークン分割だと `EXEC SQL COMMIT;` から "COMMIT" を誤抽出するため。
- `process_grep_file()` はusage_type未設定のGrepRecordを返し、`main()`内で`classify_usage_proc()`を呼ぶ方式を採用（設計書通り）。

**新たに必要になったタスク**:
- `_C_TYPE_PATTERN` 定数の追加（モジュールレベル）

### 学んだこと

**技術的な学び**:
- `[\w\s\*\[\]]*` を正規表現の文字クラスに含めるとスペースも貪欲マッチするため、その後の `\s+` が機能しなくなるケースがある。型と変数名の間のスペース分割は文字クラス外で扱う必要がある。
- Pro*C の `char localCode[] = "val";` のように変数名の後ろに `[]` がある形は、`(?:\[.*?\])?` を明示的に書く必要がある。

**プロセス上の改善点**:
- 設計書のサンプル正規表現はツールを実際に動かしてみるまで誤りに気づけなかった。設計書にテストケース例を記載すると早期発見できる。

### 次回への改善提案
- バッチスキャン最適化（Javaツールの `_batch_track_constants` 相当）: 複数 `.grep` ファイルがある場合、`track_define` が定数ごとにプロジェクト全体をスキャンするため、定数が多いと O(N_定数 × N_ファイル) になる。まとめて1パスに削減できる。
- `extract_variable_name_proc` のC型パターン（`_C_TYPE_PATTERN`）はPro*Cで使われる typedef 型名（`SQLCA_TYPE`等）に対応できていない可能性がある。実案件でのフィードバックを経て拡張する。
