# 設計書

## アーキテクチャ概要

既存テストへの最小修正 + 新規 E2E テストクラス追加。フィクスチャはすべて `tests/fixtures/intense/` 以下に配置。

```
tests/fixtures/intense/
├── java/                          ← source_dir（激し目フィクスチャ）
│   ├── com/example/
│   │   ├── constants/
│   │   │   ├── AppConstants.java      ← 大量の static final 定数
│   │   │   ├── ErrorCodes.java        ← エラーコード定数群
│   │   │   └── MessageKeys.java       ← メッセージキー定数群
│   │   ├── domain/
│   │   │   ├── Order.java             ← エンティティ（フィールド + getter + 非標準getter）
│   │   │   ├── OrderItem.java         ← 関連エンティティ
│   │   │   └── OrderStatus.java       ← enum
│   │   ├── service/
│   │   │   ├── OrderService.java      ← 定数・フィールド・getter を複雑に参照
│   │   │   ├── ValidationService.java ← 条件判定で定数参照
│   │   │   └── NotificationService.java ← return文・メソッド引数で参照
│   │   ├── repository/
│   │   │   └── OrderRepository.java   ← アノテーション付き参照
│   │   └── util/
│   │       └── CodeConverter.java     ← ローカル変数経由参照
└── grep/                          ← input_dir（grep ファイル群）
    ├── ORDER_TYPE.grep             ← 定数 ORDER_TYPE の grep 結果
    └── orderStatus.grep            ← フィールド orderStatus の grep 結果
```

## フィクスチャ設計

### AppConstants.java
```java
public class AppConstants {
    public static final String ORDER_TYPE_NORMAL = "01";
    public static final String ORDER_TYPE_EXPRESS = "02";
    public static final String ORDER_TYPE_SUBSCRIPTION = "03";
    public static final int    MAX_ORDER_ITEMS = 100;
    public static final String STATUS_PENDING = "PENDING";
    // ... 定数多数
}
```

### Order.java（エンティティ）
```java
public class Order {
    @Column(name = "order_type")
    private String orderType;      // フィールド：classスコープ
    private String orderStatus;    // フィールド：classスコープ

    // 標準 getter
    public String getOrderType() { return orderType; }
    // 非標準 getter
    public String fetchStatus() { return orderStatus; }
}
```

### OrderService.java（複合参照）
```java
public class OrderService {
    @Autowired
    private Order order;

    public void processOrder(String orderType) {  // メソッド引数
        if (orderType.equals(AppConstants.ORDER_TYPE_NORMAL)) {  // 条件判定
            String localType = AppConstants.ORDER_TYPE_EXPRESS;   // ローカル変数
            log(localType);  // ローカル変数経由
        }
        return order.getOrderType();  // getter経由
    }
}
```

## grep ファイル設計

### ORDER_TYPE.grep（定数参照を網羅）
```
com/example/constants/AppConstants.java:3:    public static final String ORDER_TYPE_NORMAL = "01";
com/example/service/OrderService.java:12:        if (orderType.equals(AppConstants.ORDER_TYPE_NORMAL)) {
com/example/service/ValidationService.java:8:        if (status.equals(AppConstants.ORDER_TYPE_NORMAL)) {
Binary file target/classes/AppConstants.class matches
com/example/util/CodeConverter.java:15:        String localOrderType = AppConstants.ORDER_TYPE_NORMAL;
...（計50行以上）
```

### orderStatus.grep（フィールド参照を網羅）
```
com/example/domain/Order.java:5:    private String orderStatus;
com/example/domain/Order.java:22:        return orderStatus;
com/example/service/OrderService.java:20:        order.fetchStatus();
...
```

## テストクラス設計

```python
class TestIntenseE2E(unittest.TestCase):
    """過激な統合テスト：重厚長大システムを模したフィクスチャで全パイプラインを検証。"""

    FIXTURE_DIR = Path(__file__).parent / "tests" / "fixtures" / "intense"
    JAVA_DIR    = FIXTURE_DIR / "java"
    GREP_DIR    = FIXTURE_DIR / "grep"

    def setUp(self):
        self.output_dir = Path(tempfile.mkdtemp())
        _ast_cache.clear()

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)
        _ast_cache.clear()

    def _run_pipeline(self, grep_file: str) -> list[GrepRecord]:
        """指定 grep ファイルでパイプライン全体を実行して全レコードを返す。"""
        ...

    def test_direct_records_cover_all_usage_types(self):
        """6種類以上の使用タイプが直接参照に含まれること。"""

    def test_binary_and_empty_lines_skipped(self):
        """バイナリ行・空行はスキップされ valid_lines に含まれないこと。"""

    def test_indirect_constant_tracked_across_files(self):
        """定数の間接参照がプロジェクト全体（複数ファイル）で検出されること。"""

    def test_indirect_field_tracked_in_class(self):
        """フィールドの間接参照が同一クラス内で検出されること。"""

    def test_getter_calls_detected(self):
        """getter呼び出しが間接（getter経由）参照として検出されること。"""

    def test_tsv_output_sorted_correctly(self):
        """TSV 出力がキーワード→ファイルパス→行番号の昇順でソートされること。"""

    def test_stats_accurate(self):
        """処理統計（total, valid, skipped）が正確であること。"""

    def test_full_cli_run(self):
        """CLI（main関数）を通じて TSV ファイルが正常出力されること。"""
```

## 実装の順序

1. 失敗テストの修正（1行追加）
2. フィクスチャディレクトリ作成
3. Java フィクスチャファイル群作成（7ファイル）
4. grep フィクスチャファイル作成（2ファイル）
5. E2E テストクラス実装
6. テスト実行・デバッグ
