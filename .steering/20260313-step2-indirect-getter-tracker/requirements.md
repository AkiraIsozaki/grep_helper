# 要求内容: ステップ2 間接参照・getter経由追跡実装

## 概要

第2段階（間接参照追跡）と第3段階（getter経由追跡）を `analyze.py` に追加する。
ステップ1で実装済みの直接参照（第1段階）の上に乗せる形で実装する。

## 対象コンポーネント

1. **F-03: IndirectTracker**
   - `determine_scope()`: 変数の種類からスコープ（project/class/method）を判定
   - `extract_variable_name()`: コード行から変数名を抽出
   - `_get_method_scope()`: AST解析でメソッドの行範囲を特定（内部ヘルパー）
   - `track_constant()`: static final定数をプロジェクト全体で追跡
   - `track_field()`: フィールドを同一クラス内で追跡
   - `track_local()`: ローカル変数を同一メソッド内で追跡

2. **F-04: GetterTracker**
   - `find_getter_names()`: getter候補名のリストを返す（命名規則 + return文解析）
   - `track_getter_calls()`: getter呼び出し箇所をプロジェクト全体で追跡

3. **main() の更新**: 第2・第3段階の呼び出しを追加

## スコープ外（次ステップ）

- F-06: Reporter（独立関数化）
- test_analyze.py（ユニットテスト）
- run.sh / setup.sh / Makefile

## 完了基準

- `python -m py_compile analyze.py` が通る
- `python -m flake8 analyze.py` が通る
- 直接参照で「定数定義」「変数代入」に分類された行から、間接参照レコードが生成される
