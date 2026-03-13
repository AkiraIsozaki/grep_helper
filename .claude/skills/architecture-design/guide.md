# アーキテクチャ設計ガイド

## 基本原則

### 1. 技術選定には理由を明記

**悪い例**:
```
- Java
- JavaFX
```

**良い例**:
```
- Java 17+ (LTS)
  - 長期サポート保証により、本番環境での安定稼働が期待できる
  - 強力な型システムと豊富な標準ライブラリにより、堅牢なアプリケーション開発が可能
  - JVM上で動作するため、クロスプラットフォーム対応が容易

- JavaFX
  - Java標準のGUIフレームワークとして、デスクトップアプリケーション開発に最適
  - FXMLによる宣言的UIレイアウトとCSSスタイリングをサポート
  - Canvas/WebViewなどリッチなUIコンポーネントを提供

- Gradle 8.x
  - Groovy/Kotlin DSLによる柔軟なビルド定義が可能
  - インクリメンタルビルドとビルドキャッシュにより高速なビルドを実現
  - JavaFXプラグイン(org.openjfx.javafxplugin)との統合が容易
```

### 2. レイヤー分離の原則

各レイヤーの責務を明確にし、依存関係を一方向に保ちます:

```
UI → Service → Data (OK)
UI ← Service (NG)
UI → Data (NG)
```

### 3. 測定可能な要件

すべてのパフォーマンス要件は測定可能な形で記述します。

## レイヤードアーキテクチャの設計

### 各レイヤーの責務

**UIレイヤー**:
```java
// 責務: ユーザー入力の受付とバリデーション
public class MainController {
    private final MatrixService matrixService;

    // OK: サービスレイヤーを呼び出す
    public void onCalculate() {
        Matrix result = matrixService.multiply(matrixA, matrixB);
        resultView.display(result);
    }

    // NG: データレイヤーを直接呼び出す
    public void onCalculate() {
        Matrix result = repository.load(matrixId); // NG
    }
}
```

**サービスレイヤー**:
```java
// 責務: ビジネスロジックの実装
public class MatrixService {
    private final MatrixRepository repository;

    // ビジネスロジック: 行列演算と結果の保存
    public Matrix multiply(Matrix a, Matrix b) {
        if (a.getColumns() != b.getRows()) {
            throw new IllegalArgumentException("行列のサイズが一致しません");
        }
        Matrix result = a.multiply(b);
        repository.save(result);
        return result;
    }
}
```

**データレイヤー**:
```java
// 責務: データの永続化
public class MatrixRepository {
    public void save(Matrix matrix) {
        storage.write(matrix);
    }
}
```

## パフォーマンス要件の設定

### 具体的な数値目標

```
GUI応答時間: 100ms以内(平均的なPC環境で)
└─ 測定方法: System.nanoTime()でボタン押下から結果表示まで計測
└─ 測定環境: CPU Core i5相当、メモリ8GB、SSD

行列演算表示: 100x100行列まで1秒以内
└─ 測定方法: ダミーデータで計測
└─ 許容範囲: 10x10で10ms、100x100で1秒、1000x1000で10秒
```

## セキュリティ設計

### データ保護の3原則

1. **最小権限の原則**
```bash
# ファイルパーミッション
chmod 600 ~/.linalgpad/data.json  # 所有者のみ読み書き
```

2. **入力検証**
```java
public void validateDimension(int rows, int cols) {
    if (rows <= 0 || cols <= 0) {
        throw new ValidationException("行列のサイズは正の整数である必要があります");
    }
    if (rows > 10000 || cols > 10000) {
        throw new ValidationException("行列のサイズは10000以内です");
    }
}
```

3. **機密情報の管理**
```bash
# 環境変数で管理
export LINALGPAD_API_KEY="xxxxx"  # コード内にハードコードしない
```

```java
// Javaコード内での取得
String apiKey = System.getenv("LINALGPAD_API_KEY");
// または properties ファイルから取得
Properties props = new Properties();
props.load(new FileInputStream("config.properties"));
String apiKey = props.getProperty("api.key");
```

## スケーラビリティ設計

### データ増加への対応

**想定データ量**: [例: 10,000件の行列データ]

**対策**:
- データのページネーション
- 古いデータのアーカイブ
- インデックスの最適化

```java
// アーカイブ機能の例: 古いデータを別ファイルに移動
public class ArchiveService {
    private final MatrixRepository repository;
    private final ArchiveStorage archiveStorage;

    public void archiveOldData(LocalDateTime olderThan) {
        List<Matrix> oldData = repository.findOlderThan(olderThan);
        archiveStorage.save(oldData);
        repository.deleteAll(oldData.stream().map(Matrix::getId).toList());
    }
}
```

## 依存関係管理

### バージョン管理方針

```groovy
// build.gradle
dependencies {
    // JavaFX - プラットフォーム固有のモジュール
    implementation 'org.openjfx:javafx-controls:21'
    implementation 'org.openjfx:javafx-fxml:21'

    // ユーティリティ - マイナーバージョンアップは自動
    implementation 'com.google.guava:guava:33.+'

    // JSON処理 - 安定版は固定
    implementation 'com.google.code.gson:gson:2.10.1'

    // テスト依存
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.+'
    testImplementation 'org.assertj:assertj-core:3.25.+'
}
```

**方針**:
- 安定版は固定バージョンで管理
- 信頼性の高いライブラリはマイナーバージョンまで許可(`+`を使用)
- テスト依存はパッチバージョンのみ自動(`+`を使用)
- `gradle dependencies` で依存ツリーを定期的に確認

## チェックリスト

- [ ] すべての技術選定に理由が記載されている
- [ ] レイヤードアーキテクチャが明確に定義されている
- [ ] パフォーマンス要件が測定可能である
- [ ] セキュリティ考慮事項が記載されている
- [ ] スケーラビリティが考慮されている
- [ ] バックアップ戦略が定義されている
- [ ] 依存関係管理のポリシーが明確である
- [ ] テスト戦略が定義されている
