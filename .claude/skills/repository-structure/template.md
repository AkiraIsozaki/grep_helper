# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
project-root/
├── src/
│   ├── main/
│   │   ├── java/              # Javaソースコード
│   │   │   └── com/example/app/
│   │   │       ├── [layer1]/  # [説明]
│   │   │       ├── [layer2]/  # [説明]
│   │   │       └── [layer3]/  # [説明]
│   │   └── resources/         # リソースファイル
│   │       └── fxml/          # JavaFX FXMLファイル
│   └── test/
│       └── java/              # テストコード
│           └── com/example/app/
│               ├── unit/          # ユニットテスト
│               ├── integration/   # 統合テスト
│               └── e2e/           # E2Eテスト
├── docs/                      # プロジェクトドキュメント
├── config/                    # 設定ファイル（該当する場合）
└── scripts/                   # ビルド・デプロイスクリプト
```

## ディレクトリ詳細

### src/main/java/ (ソースコードディレクトリ)

#### [パッケージ1]

**役割**: [説明]

**配置ファイル**:
- [ファイルパターン1]: [説明]
- [ファイルパターン2]: [説明]

**命名規則**:
- [規則1]
- [規則2]

**依存関係**:
- 依存可能: [パッケージ名]
- 依存禁止: [パッケージ名]

**例**:
```
[パッケージ名]/
├── [ExampleFile1].java
└── [ExampleFile2].java
```

#### [パッケージ2]

**役割**: [説明]

**配置ファイル**:
- [ファイルパターン1]: [説明]

**命名規則**:
- [規則1]

**依存関係**:
- 依存可能: [パッケージ名]
- 依存禁止: [パッケージ名]

### src/test/java/ (テストディレクトリ)

#### unit/

**役割**: ユニットテストの配置

**構造**:
```
src/test/java/com/example/app/unit/
└── [layer]/
    └── [ClassName]Test.java
```

**命名規則**:
- パターン: `[テスト対象クラス名]Test.java`
- 例: `TaskService.java` → `TaskServiceTest.java`

#### integration/

**役割**: 統合テストの配置

**構造**:
```
src/test/java/com/example/app/integration/
└── [feature]/
    └── [Scenario]Test.java
```

#### e2e/

**役割**: E2Eテストの配置

**構造**:
```
src/test/java/com/example/app/e2e/
└── [userscenario]/
    └── [Flow]Test.java
```

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:
- `product-requirements.md`: プロダクト要求定義書
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: リポジトリ構造定義書(本ドキュメント)
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

### src/main/resources/ (リソースディレクトリ)

**配置ファイル**:
- JavaFX FXMLファイル
- アプリケーション設定ファイル
- 画像・CSSなどのアセット

**例**:
```
src/main/resources/
├── fxml/
│   └── main-view.fxml
├── css/
│   └── styles.css
└── application.properties
```

### config/ (設定ファイルディレクトリ - 該当する場合)

**配置ファイル**:
- Checkstyle設定ファイル
- その他ツール設定ファイル

**例**:
```
config/
├── checkstyle/
│   └── checkstyle.xml
└── spotbugs/
    └── exclude-filter.xml
```

### scripts/ (スクリプトディレクトリ - 該当する場合)

**配置ファイル**:
- ビルドスクリプト
- 開発補助スクリプト

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| [種別1] | [パッケージ] | [規則] | [例] |
| [種別2] | [パッケージ] | [規則] | [例] |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | src/test/java/.../unit/ | [対象]Test.java | TaskServiceTest.java |
| 統合テスト | src/test/java/.../integration/ | [機能]Test.java | TaskCrudTest.java |
| E2Eテスト | src/test/java/.../e2e/ | [シナリオ]Test.java | UserWorkflowTest.java |

### 設定ファイル

| ファイル種別 | 配置先 | 命名規則 |
|------------|--------|---------|
| アプリケーション設定 | src/main/resources/ | application.properties |
| ビルド設定 | プロジェクトルート | build.gradle |
| コード品質 | config/ | checkstyle.xml |

## 命名規則

### パッケージ名

- **レイヤーパッケージ**: 単数形、小文字
  - 例: `service/`, `repository/`, `controller/`
- **機能パッケージ**: 小文字（ハイフン不可）
  - 例: `taskmanagement/`, `userauthentication/`

### ファイル名

- **クラスファイル**: PascalCase
  - 例: `TaskService.java`, `UserRepository.java`
- **インターフェース**: PascalCase
  - 例: `ITaskService.java`, `TaskRepository.java`
- **列挙型**: PascalCase
  - 例: `TaskStatus.java`, `Priority.java`

### テストファイル名

- パターン: `[テスト対象クラス名]Test.java`
- 例: `TaskServiceTest.java`, `TaskRepositoryTest.java`

## 依存関係のルール

### レイヤー間の依存

```
UIレイヤー (controller)
    ↓ (OK)
サービスレイヤー (service)
    ↓ (OK)
データレイヤー (repository)
```

**禁止される依存**:
- データレイヤー → サービスレイヤー
- データレイヤー → UIレイヤー
- サービスレイヤー → UIレイヤー

### モジュール間の依存

**循環依存の禁止**:
```java
// ❌ 悪い例: 循環依存
// FileA.java
import com.example.app.service.FileB;

// FileB.java
import com.example.app.service.FileA;  // 循環依存
```

**解決策**:
```java
// ✅ 良い例: 共通インターフェースの抽出
// SharedType.java
public interface SharedType { /* ... */ }

// FileA.java
import com.example.app.model.SharedType;

// FileB.java
import com.example.app.model.SharedType;
```

## スケーリング戦略

### 機能の追加

新しい機能を追加する際の配置方針:

1. **小規模機能**: 既存パッケージに配置
2. **中規模機能**: レイヤー内にサブパッケージを作成
3. **大規模機能**: 独立したモジュールとして分離

**例**:
```
src/main/java/com/example/app/
├── service/
│   ├── TaskService.java             # 既存機能
│   └── task/                        # 中規模機能の分離
│       ├── TaskService.java
│       ├── SubtaskService.java
│       └── TaskCategoryService.java
```

### ファイルサイズの管理

**ファイル分割の目安**:
- 1ファイル: 300行以下を推奨
- 300-500行: リファクタリングを検討
- 500行以上: 分割を強く推奨

**分割方法**:
```java
// 悪い例: 1ファイルに全機能
// TaskService.java (800行)

// 良い例: 責務ごとに分割
// TaskService.java (200行) - CRUD操作
// TaskValidationService.java (150行) - バリデーション
// TaskNotificationService.java (100行) - 通知処理
```

## 特殊ディレクトリ

### .steering/ (ステアリングファイル)

**役割**: 特定の開発作業における「今回何をするか」を定義

**構造**:
```
.steering/
└── [YYYYMMDD]-[task-name]/
    ├── requirements.md      # 今回の作業の要求内容
    ├── design.md            # 変更内容の設計
    └── tasklist.md          # タスクリスト
```

**命名規則**: `20250115-add-user-profile` 形式

### .claude/ (Claude Code設定)

**役割**: Claude Code設定とカスタマイズ

**構造**:
```
.claude/
├── commands/                # スラッシュコマンド
├── skills/                  # タスクモード別スキル
└── agents/                  # サブエージェント定義
```

## 除外設定

### .gitignore

プロジェクトで除外すべきファイル:
- `.gradle/`
- `build/`
- `.env`
- `.steering/` (タスク管理用の一時ファイル)
- `*.log`
- `.DS_Store`
- `*.class`
- `.idea/`
- `*.iml`

### Gradle / コード品質ツール

ツールで除外すべきディレクトリ:
- `build/`
- `.gradle/`
- `.steering/`
