# タスクリスト: analyze.py リファクタリング

## フェーズ1: 準備

- [x] analyze.py 全体を読み込んで現状把握
- [x] ステアリングファイル作成

## フェーズ2: 実装

- [x] ScopeType Enum を追加し、determine_scope() / main() を更新
- [x] extract_variable_name() の未使用 usage_type 引数を削除
- [x] find_getter_names() に source_dir 追加、get_ast() を使うよう修正
- [x] determine_scope() の except: pass を適切な処理に変更
- [x] _track_indirect_for_record() を抽出して main() をすっきりさせる

## フェーズ3: 検証

- [x] python -m unittest discover が全件パス（既存失敗3件も修正して90件全件パス）
- [x] python -m flake8 analyze.py が通る

## 実装後の振り返り

**完了日**: 2026-03-22

**計画と実績の差分**:
- 計画通りに全タスクを実施
- テストファイルの修正も必要だった（シグネチャ変更に伴う呼び出し箇所の修正）
- `_track_indirect_for_record()` をF-05セクション前に配置（F-03/F-04の関数を利用するため）

**学んだこと**:
- 引数削除・追加はテストコードも漏れなく更新が必要
- `git stash` を使って既存失敗の確認をすることで安全にリファクタリング範囲を限定できた
