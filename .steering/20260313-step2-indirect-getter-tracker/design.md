# 設計: ステップ2 間接参照・getter経由追跡実装

## analyze.py への追加位置

```
既存: F-01 GrepParser
既存: F-02 UsageClassifier
新規: F-03 IndirectTracker  ← ここに追加
新規: F-04 GetterTracker    ← ここに追加
既存: F-05 TsvWriter
既存: CLI main()            ← 第2・第3段階の呼び出しを追加
```

## シグネチャ方針（スペックからの変更点）

スペックの `ast_cache: dict` 引数はグローバル `_ast_cache` で代替（ステップ1と統一）。
`source_dir: Path` はスペックにないが、`classify_usage()` 呼び出しに必要なため追加。

## F-03: IndirectTracker 詳細設計

### determine_scope()

```python
def determine_scope(usage_type: str, code: str) -> str:
    if usage_type == "定数定義":
        return "project"
    # フィールド判定: クラスレベルの宣言
    if re.match(r'(private|protected|public)?\s+\w[\w<>\[\]]*\s+\w+\s*[=;]', stripped):
        return "class"
    return "method"
```

### extract_variable_name()

```python
# 左辺（= より前）の最後の識別子が変数名
# 例: "public static final String CODE = ..." → "CODE"
# 例: "String msg = CODE;" → "msg"
```

### _get_method_scope()（内部ヘルパー）

AST で MethodDeclaration の開始行を取得し、
ブレースカウンタで終了行を特定する。
javalang はノードの終了行を提供しないため、この方式を採用。

### track_constant()

- `source_dir.rglob("*.java")` で全Javaファイルを走査
- `\bvar_name\b` のパターンでマッチ（部分一致を避ける）
- 定義行（origin.filepath + origin.lineno）はスキップ

### track_field()

- `class_file` 内のみ走査（同一クラスに限定）
- `\bvar_name\b` でマッチ
- 定義行はスキップ

### track_local()

- `method_scope` の行範囲内のみ走査
- `\bvar_name\b` でマッチ
- 定義行はスキップ

## F-04: GetterTracker 詳細設計

### find_getter_names()

2方式を併用:
1. 命名規則: `field_name[0].upper() + field_name[1:]` → `"get" + ...`
2. return文解析: AST で `return field_name;` しているメソッドを検出

### track_getter_calls()

- `source_dir.rglob("*.java")` で全Javaファイルを走査
- `\bgetter_name\s*\(` のパターンでマッチ
- false positive は許容（もれなく優先）
- `ref_type = RefType.GETTER.value`

## main() 更新方針

```python
# 第1段階の後に追加
for record in records:  # records は直接参照
    if record.usage_type not in (UsageType.CONSTANT.value, UsageType.VARIABLE.value):
        continue
    var_name = extract_variable_name(record.code, record.usage_type)
    if not var_name:
        continue
    scope = determine_scope(record.usage_type, record.code)
    if scope == "project":
        all_records.extend(track_constant(var_name, source_dir, record, stats))
    elif scope == "class":
        class_file = _resolve_java_file(record.filepath, source_dir)
        if class_file:
            indirect = track_field(var_name, class_file, record, source_dir, stats)
            all_records.extend(indirect)
            # 第3段階: getter追跡
            for getter_name in find_getter_names(var_name, class_file):
                all_records.extend(track_getter_calls(getter_name, source_dir, record, stats))
    elif scope == "method":
        scope_range = _get_method_scope(record.filepath, source_dir, int(record.lineno))
        if scope_range:
            all_records.extend(track_local(var_name, scope_range, record, source_dir, stats))
```

## ファイルパス解決の方針

`_resolve_java_file(filepath, source_dir)` ヘルパーを追加:
- `filepath` が絶対パス → そのまま使用
- `filepath` が相対パス → `source_dir / filepath` を試みる
- 存在しない場合は None を返す
