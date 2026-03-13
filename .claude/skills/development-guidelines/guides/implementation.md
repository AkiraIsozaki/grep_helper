# 実装ガイド (Implementation Guide)

## Java 規約

### 型定義

**標準ライブラリの型を使用**:
```java
// 良い例: 標準ライブラリの型を使用
public Map<String, Integer> processItems(List<String> items) {
    Map<String, Integer> counts = new HashMap<>();
    for (String item : items) {
        counts.merge(item, 1, Integer::sum);
    }
    return counts;
}

// 悪い例: 生の型を使用
public Map processItems(List items) {  // 型安全性が失われる
    // ...
}
```

**型注釈の原則**:
```java
// 良い例: 明示的な型を使用
public double calculateTotal(List<Double> prices) {
    return prices.stream()
        .mapToDouble(Double::doubleValue)
        .sum();
}

// 悪い例: varの多用で可読性が低下
public double calculateTotal(var prices) {  // コンパイルエラー（メソッド引数にvarは使えない）
    // ...
}
```

**インターフェース vs クラス vs enum**:
```java
// インターフェース: 振る舞いの抽象化
public interface Task {
    String getId();
    String getTitle();
    boolean isCompleted();
}

// クラスによる拡張
public class ExtendedTask implements Task {
    private final String id;
    private final String title;
    private final boolean completed;
    private final String priority;

    // コンストラクタ、ゲッター省略
}

// enum: 固定の選択肢
public enum TaskStatus {
    TODO, IN_PROGRESS, COMPLETED
}

// record (Java 16+): 不変データキャリア
public record TaskId(String value) {}
```

### 命名規則

**変数・メソッド**:
```java
// 変数: camelCase、名詞
final String userName = "John";
final List<Task> taskList = new ArrayList<>();
final boolean isCompleted = true;

// メソッド: camelCase、動詞で始める
public UserData fetchUserData() { }
public boolean validateEmail(String email) { }
public double calculateTotalPrice(List<Item> items) { }

// Boolean: is, has, should, canで始める
final boolean isValid = true;
final boolean hasPermission = false;
final boolean shouldRetry = true;
final boolean canDelete = false;
```

**クラス・インターフェース**:
```java
// クラス: PascalCase、名詞
public class TaskManager { }
public class UserAuthenticationService { }

// インターフェース: PascalCase
public interface TaskRepository { }
public interface UserProfile { }

// enum: PascalCase、定数はUPPER_SNAKE_CASE
public enum TaskStatus {
    TODO, IN_PROGRESS, COMPLETED
}
```

**定数**:
```java
// UPPER_SNAKE_CASE
public static final int MAX_RETRY_COUNT = 3;
public static final String API_BASE_URL = "https://api.example.com";
public static final long DEFAULT_TIMEOUT = 5000L;

// 設定クラスの場合
public final class AppConfig {
    public static final int MAX_RETRY_COUNT = 3;
    public static final String API_BASE_URL = "https://api.example.com";
    public static final long DEFAULT_TIMEOUT = 5000L;

    private AppConfig() {} // インスタンス化を防止
}
```

**ファイル名**:
```java
// クラスファイル: PascalCase（クラス名と一致）
// TaskService.java
// UserRepository.java

// インターフェース: PascalCase
// TaskRepository.java

// enum: PascalCase
// TaskStatus.java

// テストクラス: クラス名 + Test
// TaskServiceTest.java
// UserRepositoryTest.java
```

### メソッド設計

**単一責務の原則**:
```java
// 良い例: 単一の責務
public double calculateTotalPrice(List<CartItem> items) {
    return items.stream()
        .mapToDouble(item -> item.getPrice() * item.getQuantity())
        .sum();
}

public String formatPrice(double amount) {
    return String.format("¥%,.0f", amount);
}

// 悪い例: 複数の責務
public String calculateAndFormatPrice(List<CartItem> items) {
    double total = items.stream()
        .mapToDouble(item -> item.getPrice() * item.getQuantity())
        .sum();
    return String.format("¥%,.0f", total);
}
```

**メソッドの長さ**:
- 目標: 20行以内
- 推奨: 50行以内
- 100行以上: リファクタリングを検討

**パラメータの数**:
```java
// 良い例: パラメータオブジェクトでまとめる
public record CreateTaskOptions(
    String title,
    String description,
    TaskPriority priority,
    LocalDate dueDate
) {
    // descriptionとpriorityとdueDateをOptionalにしたい場合はBuilderパターンを使用
}

public Task createTask(CreateTaskOptions options) {
    // 実装
}

// 悪い例: パラメータが多すぎる
public Task createTask(
    String title,
    String description,
    String priority,
    LocalDate dueDate,
    List<String> tags,
    String assignee
) {
    // 実装
}
```

### エラーハンドリング

**カスタム例外クラス**:
```java
// 例外クラスの定義
public class ValidationException extends RuntimeException {
    private final String field;
    private final Object value;

    public ValidationException(String message, String field, Object value) {
        super(message);
        this.field = field;
        this.value = value;
    }

    public String getField() { return field; }
    public Object getValue() { return value; }
}

public class NotFoundException extends RuntimeException {
    private final String resource;
    private final String id;

    public NotFoundException(String resource, String id) {
        super(resource + " not found: " + id);
        this.resource = resource;
        this.id = id;
    }

    public String getResource() { return resource; }
    public String getId() { return id; }
}

public class DatabaseException extends RuntimeException {
    public DatabaseException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

**エラーハンドリングパターン**:
```java
// 良い例: 適切なエラーハンドリング
public Task getTask(String id) {
    try {
        Optional<Task> task = repository.findById(id);

        return task.orElseThrow(
            () -> new NotFoundException("Task", id)
        );
    } catch (NotFoundException e) {
        // 予期される例外: 適切に処理
        logger.warn("タスクが見つかりません: {}", id);
        throw e;
    } catch (Exception e) {
        // 予期しない例外: ラップして上位に伝播
        throw new DatabaseException("タスクの取得に失敗しました", e);
    }
}

// 悪い例: 例外を無視
public Task getTask(String id) {
    try {
        return repository.findById(id).orElse(null);
    } catch (Exception e) {
        return null; // エラー情報が失われる
    }
}
```

**エラーメッセージ**:
```java
// 良い例: 具体的で解決策を示す
throw new ValidationException(
    "タイトルは1-200文字で入力してください。現在の文字数: " + title.length(),
    "title",
    title
);

// 悪い例: 曖昧で役に立たない
throw new IllegalArgumentException("Invalid input");
```

### 並行処理

**CompletableFutureの使用**:
```java
// 良い例: CompletableFutureで非同期処理
public CompletableFuture<List<Task>> fetchUserTasks(String userId) {
    return CompletableFuture.supplyAsync(() -> {
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new NotFoundException("User", userId));
        return taskRepository.findByUserId(user.getId());
    }).exceptionally(e -> {
        logger.error("タスクの取得に失敗", e);
        throw new RuntimeException(e);
    });
}

// 同期処理で十分な場合はシンプルに
public List<Task> fetchUserTasks(String userId) {
    User user = userRepository.findById(userId)
        .orElseThrow(() -> new NotFoundException("User", userId));
    return taskRepository.findByUserId(user.getId());
}
```

**並列処理**:
```java
// 良い例: parallelStreamまたはCompletableFutureで並列実行
public List<User> fetchMultipleUsers(List<String> ids) {
    List<CompletableFuture<User>> futures = ids.stream()
        .map(id -> CompletableFuture.supplyAsync(
            () -> userRepository.findById(id).orElseThrow()
        ))
        .toList();

    return futures.stream()
        .map(CompletableFuture::join)
        .toList();
}

// 悪い例: 逐次実行（必要がないのに直列処理）
public List<User> fetchMultipleUsers(List<String> ids) {
    List<User> users = new ArrayList<>();
    for (String id : ids) {
        User user = userRepository.findById(id).orElseThrow(); // 遅い
        users.add(user);
    }
    return users;
}
```

## コメント規約

### ドキュメントコメント

**Javadoc形式**:
```java
/**
 * タスクを作成する。
 *
 * <p>指定されたデータに基づいて新しいタスクを作成し、
 * リポジトリに永続化する。</p>
 *
 * @param data 作成するタスクのデータ
 * @return 作成されたタスク
 * @throws ValidationException データが不正な場合
 * @throws DatabaseException データベースエラーの場合
 *
 * <pre>{@code
 * Task task = service.createTask(new CreateTaskData(
 *     "新しいタスク",
 *     TaskPriority.HIGH
 * ));
 * }</pre>
 */
public Task createTask(CreateTaskData data) {
    // 実装
}
```

### インラインコメント

**良いコメント**:
```java
// 理由を説明
// キャッシュを無効化して最新データを取得
cache.clear();

// 複雑なロジックを説明
// Kadaneのアルゴリズムで最大部分配列和を計算
// 時間計算量: O(n)
double maxSoFar = arr[0];
double maxEndingHere = arr[0];

// TODO・FIXMEを活用
// TODO: キャッシュ機能を実装 (Issue #123)
// FIXME: 大量データでパフォーマンス劣化 (Issue #456)
// HACK: 一時的な回避策、後でリファクタリング必要
```

**悪いコメント**:
```java
// コードの内容を繰り返すだけ
// iを1増やす
i++;

// 古い情報
// このコードは2020年に追加された (不要な情報)

// コメントアウトされたコード
// OldImplementation old = new OldImplementation();  // 削除すべき
```

## セキュリティ

### 入力検証

```java
// 良い例: 厳密な検証
public void validateEmail(String email) {
    if (email == null || email.isBlank()) {
        throw new ValidationException("メールアドレスは必須です", "email", email);
    }

    String emailRegex = "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$";
    if (!email.matches(emailRegex)) {
        throw new ValidationException("メールアドレスの形式が不正です", "email", email);
    }

    if (email.length() > 254) {
        throw new ValidationException("メールアドレスが長すぎます", "email", email);
    }
}

// 悪い例: 検証なし
public void validateEmail(String email) {
    // 検証なし
}
```

### 機密情報の管理

```java
// 良い例: 環境変数から読み込み
String apiKey = System.getenv("API_KEY");
if (apiKey == null || apiKey.isBlank()) {
    throw new IllegalStateException("API_KEY環境変数が設定されていません");
}

// 悪い例: ハードコード
String apiKey = "sk-1234567890abcdef"; // 絶対にしない！
```

## パフォーマンス

### データ構造の選択

```java
// 良い例: MapでO(1)アクセス
Map<String, User> userMap = users.stream()
    .collect(Collectors.toMap(User::getId, Function.identity()));
User user = userMap.get(userId); // O(1)

// 悪い例: ListでO(n)検索
User user = users.stream()
    .filter(u -> u.getId().equals(userId))
    .findFirst()
    .orElse(null); // O(n)
```

### ループの最適化

```java
// 良い例: 拡張for文を使用
for (Item item : items) {
    process(item);
}

// 良い例: Stream APIを活用
items.stream()
    .filter(Item::isActive)
    .forEach(this::process);

// 悪い例: インデックスベースでsizeを毎回呼び出し（実際にはJITで最適化されるが意図が不明瞭）
for (int i = 0; i < items.size(); i++) {
    process(items.get(i));
}
```

### メモ化

```java
// 計算結果のキャッシュ
private final Map<String, Result> cache = new ConcurrentHashMap<>();

public Result expensiveCalculation(String input) {
    return cache.computeIfAbsent(input, key -> {
        // 重い計算
        return doExpensiveWork(key);
    });
}
```

## テストコード

### テストの構造 (Given-When-Then)

```java
class TaskServiceTest {

    private TaskRepository mockRepository;
    private TaskService service;

    @BeforeEach
    void setUp() {
        mockRepository = mock(TaskRepository.class);
        service = new TaskService(mockRepository);
    }

    @Nested
    @DisplayName("create メソッド")
    class Create {

        @Test
        @DisplayName("正常なデータでタスクを作成できる")
        void createsTaskWithValidData() {
            // Given: 準備
            CreateTaskData taskData = new CreateTaskData(
                "テストタスク",
                "テスト用の説明"
            );
            when(mockRepository.save(any(Task.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

            // When: 実行
            Task result = service.create(taskData);

            // Then: 検証
            assertNotNull(result);
            assertNotNull(result.getId());
            assertEquals("テストタスク", result.getTitle());
            assertEquals("テスト用の説明", result.getDescription());
            assertNotNull(result.getCreatedAt());
        }

        @Test
        @DisplayName("タイトルが空の場合ValidationExceptionをスローする")
        void throwsWhenTitleIsEmpty() {
            // Given: 準備
            CreateTaskData invalidData = new CreateTaskData("", null);

            // When/Then: 実行と検証
            assertThrows(ValidationException.class,
                () -> service.create(invalidData)
            );
        }
    }
}
```

### モックの作成

```java
// 良い例: Mockitoを使用したモック
@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @Mock
    private TaskRepository mockRepository;

    @InjectMocks
    private TaskService service;

    @Test
    void findExistingTask() {
        // テストごとに動作を設定
        Task mockTask = new Task("existing-id", "テストタスク");
        when(mockRepository.findById("existing-id"))
            .thenReturn(Optional.of(mockTask));
        when(mockRepository.findById("non-existing-id"))
            .thenReturn(Optional.empty());

        // 実行と検証
        Task found = service.getTask("existing-id");
        assertEquals("テストタスク", found.getTitle());

        assertThrows(NotFoundException.class,
            () -> service.getTask("non-existing-id")
        );
    }
}
```

## リファクタリング

### マジックナンバーの排除

```java
// 良い例: 定数を定義
private static final int MAX_RETRY_COUNT = 3;
private static final long RETRY_DELAY_MS = 1000L;

public Data fetchWithRetry() throws InterruptedException {
    for (int i = 0; i < MAX_RETRY_COUNT; i++) {
        try {
            return fetchData();
        } catch (Exception e) {
            if (i < MAX_RETRY_COUNT - 1) {
                Thread.sleep(RETRY_DELAY_MS);
            }
        }
    }
    throw new RuntimeException("最大リトライ回数を超過しました");
}

// 悪い例: マジックナンバー
public Data fetchWithRetry() throws InterruptedException {
    for (int i = 0; i < 3; i++) {
        try {
            return fetchData();
        } catch (Exception e) {
            if (i < 2) {
                Thread.sleep(1000);
            }
        }
    }
    throw new RuntimeException("失敗");
}
```

### メソッドの抽出

```java
// 良い例: メソッドを抽出
public void processOrder(Order order) {
    validateOrder(order);
    calculateTotal(order);
    applyDiscounts(order);
    saveOrder(order);
}

private void validateOrder(Order order) {
    if (order.getItems() == null || order.getItems().isEmpty()) {
        throw new ValidationException("商品が選択されていません", "items", order.getItems());
    }
}

private void calculateTotal(Order order) {
    double total = order.getItems().stream()
        .mapToDouble(item -> item.getPrice() * item.getQuantity())
        .sum();
    order.setTotal(total);
}

// 悪い例: 長いメソッド
public void processOrder(Order order) {
    if (order.getItems() == null || order.getItems().isEmpty()) {
        throw new ValidationException("商品が選択されていません", "items", order.getItems());
    }

    double total = order.getItems().stream()
        .mapToDouble(item -> item.getPrice() * item.getQuantity())
        .sum();
    order.setTotal(total);

    if (order.getCoupon() != null) {
        order.setTotal(order.getTotal() - order.getTotal() * order.getCoupon().getDiscountRate());
    }

    repository.save(order);
}
```

## チェックリスト

実装完了前に確認:

### コード品質
- [ ] 命名が明確で一貫している
- [ ] メソッドが単一の責務を持っている
- [ ] マジックナンバーがない
- [ ] 型が適切に定義されている（ジェネリクスの活用）
- [ ] エラーハンドリングが実装されている

### セキュリティ
- [ ] 入力検証が実装されている
- [ ] 機密情報がハードコードされていない
- [ ] SQLインジェクション対策がされている（PreparedStatement等）

### パフォーマンス
- [ ] 適切なデータ構造を使用している
- [ ] 不要な計算を避けている
- [ ] ループが最適化されている

### テスト
- [ ] JUnit 5でユニットテストが書かれている
- [ ] テストがパスする（`./gradlew test`）
- [ ] エッジケースがカバーされている

### ドキュメント
- [ ] クラス・メソッドにJavadocコメントがある
- [ ] 複雑なロジックにコメントがある
- [ ] TODOやFIXMEが記載されている（該当する場合）

### ツール
- [ ] コンパイルエラーがない
- [ ] Gradleビルドが成功する（`./gradlew build`）
- [ ] コードフォーマットが統一されている
