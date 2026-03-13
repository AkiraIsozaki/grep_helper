# リポジトリ構造定義書作成ガイド

## 基本原則

### 1. 役割の明確化

各ディレクトリ（パッケージ）は単一の明確な役割を持つべきです。

**悪い例**:
```
src/main/java/com/example/app/
├── stuff/           # 曖昧
├── misc/            # 雑多
└── utils/           # 汎用的すぎる
```

**良い例**:
```
src/main/java/com/example/app/
├── controller/      # UIコントローラー実装
├── service/         # ビジネスロジック
├── repository/      # データ永続化
└── validator/       # 入力検証
```

### 2. レイヤー分離の徹底

アーキテクチャのレイヤー構造をパッケージ構造に反映させます:

```
src/main/java/com/example/app/
├── ui/              # UIレイヤー
│   └── controller/  # JavaFXコントローラー
├── service/         # サービスレイヤー
│   └── task/        # タスク管理サービス
└── repository/      # データレイヤー
    └── task/        # タスクリポジトリ
```

### 3. 技術要素ベースの分割(基本)

関連する技術要素ごとにパッケージを分割します:

**基本構造**:
```
src/main/java/com/example/app/
├── controller/      # JavaFXコントローラー
├── service/         # ビジネスロジック
├── repository/      # データ永続化
└── model/           # ドメインモデル・DTO
```

**レイヤー構造との対応**:
```
UI/プレゼンテーションレイヤー → controller/, view/
サービスレイヤー              → service/
データレイヤー                → repository/, storage/
```

## ディレクトリ構造の設計

### レイヤー構造の表現

```java
// 悪い例: 平坦な構造
src/main/java/com/example/app/
├── TaskController.java
├── TaskService.java
├── TaskRepository.java
├── UserController.java
├── UserService.java
└── UserRepository.java

// 良い例: レイヤーを明確に
src/main/java/com/example/app/
├── controller/
│   ├── TaskController.java
│   └── UserController.java
├── service/
│   ├── TaskService.java
│   └── UserService.java
└── repository/
    ├── TaskRepository.java
    └── UserRepository.java
```

### テストディレクトリの配置

**推奨構造**:
```
project/
├── src/
│   ├── main/java/com/example/app/
│   │   └── service/
│   │       └── TaskService.java
│   └── test/java/com/example/app/
│       ├── unit/
│       │   └── service/
│       │       └── TaskServiceTest.java
│       ├── integration/
│       └── e2e/
```

**理由**:
- Gradleの標準ディレクトリレイアウトに準拠
- テストコードが本番コードと分離
- ビルド時にテストを除外しやすい
- テストタイプごとに整理可能

## 命名規則のベストプラクティス

### パッケージ名の原則

**1. 単数形・小文字を使う (Javaパッケージの慣例)**
```
✅ service/
✅ repository/
✅ controller/

❌ Services/
❌ repositories/
❌ Controller/
```

理由: Javaパッケージ命名規約に準拠（小文字、単数形が一般的）

**2. すべて小文字を使う**
```
✅ taskmanagement/
✅ userauthentication/

❌ TaskManagement/
❌ userAuthentication/
```

理由: Javaパッケージ命名規約では小文字のみ使用

**3. 具体的な名前を使う**
```
✅ validator/         # 入力検証
✅ formatter/         # データ整形
✅ parser/            # データ解析

❌ util/              # 汎用的すぎる
❌ helper/            # 曖昧
❌ common/            # 意味不明
```

### ファイル名の原則

**1. クラスファイル: PascalCase + 役割接尾辞**
```java
// サービスクラス
TaskService.java
UserAuthenticationService.java

// リポジトリクラス
TaskRepository.java
UserRepository.java

// コントローラークラス
TaskController.java
```

**2. インターフェース: PascalCase + 役割接尾辞（またはI接頭辞）**
```java
// インターフェース定義
TaskService.java          // インターフェース
TaskServiceImpl.java      // 実装クラス

// またはI接頭辞パターン
ITaskService.java
TaskServiceImpl.java
```

**3. モデル/DTO: PascalCase**
```java
// ドメインモデル
Task.java
UserProfile.java

// DTO
TaskDto.java
UserProfileDto.java
```

**4. 定数クラス: PascalCase**
```java
// 定数定義
ApiEndpoints.java
ErrorMessages.java
```

**5. 列挙型: PascalCase**
```java
// Enum定義
TaskStatus.java
Priority.java
```

## 依存関係の管理

### レイヤー間の依存ルール

```java
// ✅ 良い例: 上位レイヤーから下位レイヤーへの依存
// controller/TaskController.java
import com.example.app.service.TaskService;

public class TaskController {
    private final TaskService taskService;

    public TaskController(TaskService taskService) {
        this.taskService = taskService;
    }
}

// ❌ 悪い例: 下位レイヤーから上位レイヤーへの依存
// service/TaskService.java
import com.example.app.controller.TaskController;  // 禁止！
```

### 循環依存の回避

**問題のあるコード**:
```java
// service/TaskService.java
import com.example.app.service.UserService;

public class TaskService {
    private final UserService userService;

    public TaskService(UserService userService) {
        this.userService = userService;
    }
}

// service/UserService.java
import com.example.app.service.TaskService;  // 循環依存！

public class UserService {
    private final TaskService taskService;

    public UserService(TaskService taskService) {
        this.taskService = taskService;
    }
}
```

**解決策1: 共通のインターフェースを抽出**
```java
// model/ITaskService.java
public interface ITaskService { /* ... */ }

// model/IUserService.java
public interface IUserService { /* ... */ }

// service/TaskService.java
import com.example.app.model.IUserService;

public class TaskService implements ITaskService {
    private final IUserService userService;

    public TaskService(IUserService userService) {
        this.userService = userService;
    }
}

// service/UserService.java
import com.example.app.model.ITaskService;

public class UserService implements IUserService {
    private final ITaskService taskService;

    public UserService(ITaskService taskService) {
        this.taskService = taskService;
    }
}
```

**解決策2: 依存関係を見直す**
```java
// 共通の機能を別サービスに抽出
// service/NotificationService.java
public class NotificationService {
    public void notifyTaskAssignment(String taskId, String userId) {
        // 通知処理
    }
}

// service/TaskService.java
import com.example.app.service.NotificationService;

public class TaskService {
    private final NotificationService notificationService;

    public TaskService(NotificationService notificationService) {
        this.notificationService = notificationService;
    }
}

// service/UserService.java
import com.example.app.service.NotificationService;

public class UserService {
    private final NotificationService notificationService;

    public UserService(NotificationService notificationService) {
        this.notificationService = notificationService;
    }
}
```

## スケーリング戦略

### 推奨構造

**標準パターン**:
```
src/main/java/com/example/app/
├── controller/
│   └── TaskController.java
├── service/
│   ├── TaskService.java
│   └── UserService.java
├── repository/
│   ├── TaskRepository.java
│   └── UserRepository.java
├── model/
│   ├── Task.java
│   └── User.java
├── validator/
│   └── TaskValidator.java
└── App.java
```

**理由**:
- レイヤーごとに責務が明確
- 後からのリファクタリングが不要
- チーム開発で統一しやすい

### モジュール分離のタイミング

**分離を検討する兆候**:
1. パッケージ内のファイル数が10個以上
2. 関連する機能がまとまっている
3. 独立してテスト可能
4. 他の機能への依存が少ない

**分離の手順**:
```java
// Before: 全てservice/に配置
service/
├── TaskService.java
├── TaskValidationService.java
├── TaskNotificationService.java
├── UserService.java
└── UserAuthService.java

// After: 機能ごとにサブパッケージ化
service/
├── task/
│   ├── TaskService.java
│   ├── TaskValidationService.java
│   └── TaskNotificationService.java
└── user/
    ├── UserService.java
    └── UserAuthService.java
```

## 特殊なケースの対応

### 共有コードの配置

**shared/ または common/ パッケージ**
```
src/main/java/com/example/app/
├── shared/
│   ├── util/             # 汎用ユーティリティ
│   ├── model/            # 共通モデル
│   └── constant/         # 共通定数
├── controller/
├── service/
└── repository/
```

**ルール**:
- 本当に複数のレイヤーで使われるもののみ
- 単一レイヤーでしか使わないものは含めない

### 設定ファイルの管理(該当する場合)

```
src/main/resources/
├── application.properties    # アプリケーション設定
└── fxml/                     # JavaFX FXMLファイル
```

### ビルドスクリプトの管理(該当する場合)

```
scripts/
├── build.sh                  # ビルドスクリプト
└── run.sh                    # 実行スクリプト
```

## ドキュメント配置

### ドキュメントの種類と配置先

**プロジェクトルート**:
- `README.md`: プロジェクト概要
- `CONTRIBUTING.md`: 貢献ガイド
- `LICENSE`: ライセンス

**docs/ ディレクトリ**:
- `product-requirements.md`: PRD
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: 本ドキュメント
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

**ソースコード内**:
- Javadocコメント: クラス・メソッドの説明

## チェックリスト

- [ ] 各パッケージの役割が明確に定義されている
- [ ] レイヤー構造がパッケージに反映されている
- [ ] 命名規則が一貫している
- [ ] テストコードの配置方針が決まっている
- [ ] 依存関係のルールが明確である
- [ ] 循環依存がない
- [ ] スケーリング戦略が考慮されている
- [ ] 共有コードの配置ルールが定義されている
- [ ] 設定ファイルの管理方法が決まっている
- [ ] ドキュメントの配置場所が明確である
