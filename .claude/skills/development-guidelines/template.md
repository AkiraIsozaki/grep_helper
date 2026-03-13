# 開発ガイドライン (Development Guidelines)

## コーディング規約

### 命名規則

#### 変数・メソッド

**Java**:
```java
// 良い例
UserProfile userProfileData = userService.fetchUserProfile();
public int calculateTotalPrice(List<CartItem> items) { }

// 悪い例
Object data = fetch();
public int calc(List<?> arr) { }
```

**原則**:
- 変数: camelCase、名詞または名詞句
- メソッド: camelCase、動詞で始める
- 定数: UPPER_SNAKE_CASE（`static final`）
- Boolean: `is`, `has`, `should`で始める

#### クラス・インターフェース

```java
// クラス: PascalCase、名詞
public class TaskManager { }
public class UserAuthenticationService { }

// インターフェース: PascalCase、I接頭辞なし（Java慣例）
public interface TaskRepository { }
public interface Task { }

// 列挙型: PascalCase、値はUPPER_SNAKE_CASE
public enum TaskStatus {
    TODO,
    IN_PROGRESS,
    COMPLETED
}
```

### コードフォーマット

**インデント**: 4スペース

**行の長さ**: 最大120文字

**例**:
```java
// Java コードフォーマット例
public class MatrixOperations {

    private final int rows;
    private final int cols;

    public MatrixOperations(int rows, int cols) {
        this.rows = rows;
        this.cols = cols;
    }

    public double[][] multiply(double[][] a, double[][] b) {
        // 実装
    }
}
```

### コメント規約

**クラス・メソッドのドキュメント（Javadoc）**:
```java
/**
 * タスクの合計数を計算する。
 *
 * @param tasks  計算対象のタスクリスト
 * @param filter フィルター条件（nullの場合フィルターなし）
 * @return タスクの合計数
 * @throws ValidationException タスクリストが不正な場合
 */
public int countTasks(List<Task> tasks, TaskFilter filter) {
    // 実装
}
```

**インラインコメント**:
```java
// 良い例: なぜそうするかを説明
// キャッシュを無効化して、最新データを取得
cache.clear();

// 悪い例: 何をしているか（コードを見れば分かる）
// キャッシュをクリアする
cache.clear();
```

### エラーハンドリング

**原則**:
- 予期されるエラー: 適切な例外クラスを定義
- 予期しないエラー: 上位に伝播
- 例外を無視しない

**例**:
```java
// 例外クラス定義
public class ValidationException extends RuntimeException {

    private final String field;
    private final Object value;

    public ValidationException(String message, String field, Object value) {
        super(message);
        this.field = field;
        this.value = value;
    }

    public String getField() {
        return field;
    }

    public Object getValue() {
        return value;
    }
}

// エラーハンドリング
try {
    Task task = taskService.create(data);
} catch (ValidationException e) {
    System.err.printf("検証エラー [%s]: %s%n", e.getField(), e.getMessage());
    // ユーザーにフィードバック
} catch (Exception e) {
    System.err.println("予期しないエラー: " + e.getMessage());
    throw e; // 上位に伝播
}
```

## Git運用ルール

### ブランチ戦略

**ブランチ種別**:
- `main`: 本番環境にデプロイ可能な状態
- `develop`: 開発の最新状態
- `feature/[機能名]`: 新機能開発
- `fix/[修正内容]`: バグ修正
- `refactor/[対象]`: リファクタリング

**フロー**:
```
main
  └─ develop
      ├─ feature/matrix-operations
      ├─ feature/vector-display
      └─ fix/determinant-calculation
```

### コミットメッセージ規約

**フォーマット**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type**:
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント
- `style`: コードフォーマット
- `refactor`: リファクタリング
- `test`: テスト追加・修正
- `chore`: ビルド、補助ツール等

**例**:
```
feat(matrix): 行列の固有値計算機能を追加

ユーザーが行列の固有値を計算できるようにしました。
- Matrixクラスにeigenvaluesメソッドを追加
- 固有値計算結果の表示パネルを実装
- 2x2および3x3行列に対応

Closes #123
```

### プルリクエストプロセス

**作成前のチェック**:
- [ ] 全てのテストがパス (`./gradlew test`)
- [ ] Lintエラーがない
- [ ] コンパイルが通る (`./gradlew build`)
- [ ] 競合が解決されている

**PRテンプレート**:
```markdown
## 概要
[変更内容の簡潔な説明]

## 変更理由
[なぜこの変更が必要か]

## 変更内容
- [変更点1]
- [変更点2]

## テスト
- [ ] ユニットテスト追加
- [ ] 手動テスト実施

## スクリーンショット（該当する場合）
[画像]

## 関連Issue
Closes #[Issue番号]
```

**レビュープロセス**:
1. セルフレビュー
2. 自動テスト実行
3. レビュアーアサイン
4. レビューフィードバック対応
5. 承認後マージ

## テスト戦略

### テストの種類

#### ユニットテスト

**対象**: 個別のメソッド・クラス

**カバレッジ目標**: 80%

**例**:
```java
class TaskServiceTest {

    private TaskRepository mockRepository;
    private TaskService service;

    @BeforeEach
    void setUp() {
        mockRepository = mock(TaskRepository.class);
        service = new TaskService(mockRepository);
    }

    @Test
    void create_validData_createsTask() {
        Task task = service.create("テストタスク", "説明");

        assertNotNull(task.getId());
        assertEquals("テストタスク", task.getTitle());
    }

    @Test
    void create_emptyTitle_throwsValidationException() {
        assertThrows(ValidationException.class, () -> {
            service.create("", "説明");
        });
    }
}
```

#### 統合テスト

**対象**: 複数コンポーネントの連携

**例**:
```java
class TaskCrudIntegrationTest {

    private TaskService taskService;

    @BeforeEach
    void setUp() {
        taskService = new TaskService(new InMemoryTaskRepository());
    }

    @Test
    void taskCrud_createReadUpdateDelete_succeeds() {
        // 作成
        Task created = taskService.create("テスト", "説明");

        // 取得
        Task found = taskService.findById(created.getId());
        assertEquals("テスト", found.getTitle());

        // 更新
        taskService.update(created.getId(), "更新後", null);
        Task updated = taskService.findById(created.getId());
        assertEquals("更新後", updated.getTitle());

        // 削除
        taskService.delete(created.getId());
        assertNull(taskService.findById(created.getId()));
    }
}
```

#### E2Eテスト

**対象**: ユーザーシナリオ全体

**例**:
```java
class MatrixOperationFlowTest {

    private LinAlgPadApp app;

    @BeforeEach
    void setUp() {
        app = new LinAlgPadApp();
    }

    @Test
    void userCanInputMatrixAndComputeDeterminant() {
        // 行列入力
        app.inputMatrix(new double[][]{{1, 2}, {3, 4}});
        assertTrue(app.getOutput().contains("行列を入力しました"));

        // 行列表示
        app.showMatrix();
        assertTrue(app.getOutput().contains("1.0  2.0"));

        // 行列式計算
        app.computeDeterminant();
        assertTrue(app.getOutput().contains("-2.0"));
    }
}
```

### テスト命名規則

**パターン**: `[対象]_[条件]_[期待結果]`

**例**:
```java
// 良い例
@Test void create_emptyTitle_throwsValidationException() { }
@Test void findById_existingId_returnsTask() { }
@Test void delete_nonExistentId_throwsNotFoundException() { }

// 悪い例
@Test void test1() { }
@Test void works() { }
@Test void shouldWorkCorrectly() { }
```

### モック・スタブの使用

**原則**:
- 外部依存（API、DB、ファイルシステム）はモック化
- ビジネスロジックは実装を使用

**例**:
```java
// Mockitoを使用してリポジトリをモック化
TaskRepository mockRepository = mock(TaskRepository.class);
when(mockRepository.findById(1L)).thenReturn(Optional.of(sampleTask));
when(mockRepository.findAll()).thenReturn(List.of(sampleTask));

// サービスは実際の実装を使用
TaskService service = new TaskService(mockRepository);
```

## コードレビュー基準

### レビューポイント

**機能性**:
- [ ] 要件を満たしているか
- [ ] エッジケースが考慮されているか
- [ ] エラーハンドリングが適切か

**可読性**:
- [ ] 命名が明確か
- [ ] コメントが適切か
- [ ] 複雑なロジックが説明されているか

**保守性**:
- [ ] 重複コードがないか
- [ ] 責務が明確に分離されているか
- [ ] 変更の影響範囲が限定的か

**パフォーマンス**:
- [ ] 不要な計算がないか
- [ ] メモリリークの可能性がないか
- [ ] データ構造やアルゴリズムが適切か

**セキュリティ**:
- [ ] 入力検証が適切か
- [ ] 機密情報がハードコードされていないか
- [ ] 権限チェックが実装されているか

### レビューコメントの書き方

**建設的なフィードバック**:
```markdown
## 良い例
この実装だと、行列サイズが大きくなった時にパフォーマンスが劣化する可能性があります。
代わりに、ストラッセンのアルゴリズムを検討してはどうでしょうか？

## 悪い例
この書き方は良くないです。
```

**優先度の明示**:
- `[必須]`: 修正必須
- `[推奨]`: 修正推奨
- `[提案]`: 検討してほしい
- `[質問]`: 理解のための質問

## 開発環境セットアップ

### 必要なツール

| ツール | バージョン | インストール方法 |
|--------|-----------|-----------------|
| Java (JDK) | 17+ | devcontainer に含まれる |
| Gradle | 8.x | Gradle Wrapper (`./gradlew`) を使用 |
| JavaFX | 17+ | Gradleの依存関係で管理 |

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone [URL]
cd LinAlgPad

# 2. ビルドと依存関係の解決
./gradlew build

# 3. テストの実行
./gradlew test

# 4. アプリケーションの起動
./gradlew run
```

### 推奨開発ツール（該当する場合）

- VS Code + Extension Pack for Java: Java開発の基本拡張機能
- VS Code + Gradle for Java: Gradleタスクの管理と実行
