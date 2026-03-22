# 設計: analyze.py リファクタリング

## 変更内容

### 1. ScopeType Enum 追加（Enum/データモデルセクション）

```python
class ScopeType(Enum):
    PROJECT = "project"
    CLASS = "class"
    METHOD = "method"
```

`determine_scope()` の戻り値と `main()` の比較を `ScopeType.PROJECT.value` 等に変更。

### 2. extract_variable_name() の usage_type 削除

- 引数から `usage_type: str` を削除
- `# noqa: ARG001` コメントも削除
- docstring 更新
- 呼び出し元（`main()`）でも引数削除

### 3. find_getter_names() に source_dir 追加

- シグネチャ: `find_getter_names(field_name: str, class_file: Path, source_dir: Path) -> list[str]`
- 内部の `_ast_cache` 直接操作を `get_ast(str(class_file), source_dir)` に置換
- 呼び出し元（`main()`）で `source_dir` を渡す

### 4. determine_scope() の except: pass 修正

- `except Exception:` の `pass` を削除
- フォールバック時の処理はそのまま（ASTが使えない場合は正規表現に委譲）
- ただし `stats` 引数を追加せず、単純に except 節でフォールバック継続（コメント追記）

### 5. _track_indirect_for_record() 関数抽出

```python
def _track_indirect_for_record(
    record: GrepRecord,
    source_dir: Path,
    stats: ProcessStats,
) -> list[GrepRecord]:
```

`main()` の間接追跡ループ内ロジックをこの関数に移動。
