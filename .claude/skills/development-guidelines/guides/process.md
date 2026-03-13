# プロセスガイド (Process Guide)

## 基本原則

### 1. 具体例を豊富に含める

抽象的なルールだけでなく、具体的なコード例を提示します。

**悪い例**:
```
変数名は分かりやすくすること
```

**良い例**:
```java
// ✅ 良い例: 役割が明確
UserAuthenticationService userAuthentication = new UserAuthenticationService();
MatrixRepository matrixRepository = new MatrixRepository();

// ❌ 悪い例: 曖昧
Object auth = new Service();
Object repo = new Repository();
```

### 2. 理由を説明する

「なぜそうするのか」を明確にします。

**例**:
```
## エラーを無視しない

理由: エラーを無視すると、問題の原因究明が困難になります。
予期されるエラーは適切に処理し、予期しないエラーは上位に伝播させて
ログに記録できるようにします。
```

### 3. 測定可能な基準を設定

曖昧な表現を避け、具体的な数値を示します。

**悪い例**:
```
コードカバレッジは高く保つこと
```

**良い例**:
```
コードカバレッジ目標:
- ユニットテスト: 80%以上
- 統合テスト: 60%以上
- E2Eテスト: 主要フロー100%
```

## Git運用ルール

### ブランチ戦略（Git Flow採用）

**Git Flowとは**:
Vincent Driessenが提唱した、機能開発・リリース・ホットフィックスを体系的に管理するブランチモデル。明確な役割分担により、チーム開発での並行作業と安定したリリースを実現します。

**ブランチ構成**:
```
main (本番環境)
└── develop (開発・統合環境)
    ├── feature/* (新機能開発)
    ├── fix/* (バグ修正)
    └── release/* (リリース準備)※必要に応じて
```

**運用ルール**:
- **main**: 本番リリース済みの安定版コードのみを保持。タグでバージョン管理
- **develop**: 次期リリースに向けた最新の開発コードを統合。CIでの自動テスト実施
- **feature/\*、fix/\***: developから分岐し、作業完了後にPRでdevelopへマージ
- **直接コミット禁止**: すべてのブランチでPRレビューを必須とし、コード品質を担保
- **マージ方針**: feature→develop は squash merge、develop→main は merge commit を推奨

**Git Flowのメリット**:
- ブランチの役割が明確で、複数人での並行開発がしやすい
- 本番環境(main)が常にクリーンな状態に保たれる
- 緊急対応時はhotfixブランチで迅速に対応可能（必要に応じて導入）

### コミットメッセージの規約

**Conventional Commitsを推奨**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type一覧**:
```
feat: 新機能 (minor version up)
fix: バグ修正 (patch version up)
docs: ドキュメント
style: フォーマット (コードの動作に影響なし)
refactor: リファクタリング
perf: パフォーマンス改善
test: テスト追加・修正
build: ビルドシステム
ci: CI/CD設定
chore: その他 (依存関係更新など)

BREAKING CHANGE: 破壊的変更 (major version up)
```

**良いコミットメッセージの例**:

```
feat(matrix): 行列の固有値計算機能を追加

ユーザーが行列の固有値と固有ベクトルを計算できるようになりました。

実装内容:
- MatrixモデルにeigenValues()メソッド追加
- GUIに固有値計算パネル追加
- 計算結果の可視化機能実装

破壊的変更:
- Matrix型の構造が変更されました
- 既存の保存データはマイグレーションが必要です

Closes #123
BREAKING CHANGE: Matrixクラスにdimension必須フィールド追加
```

### プルリクエストのテンプレート

**効果的なPRテンプレート**:

```markdown
## 変更の種類
- [ ] 新機能 (feat)
- [ ] バグ修正 (fix)
- [ ] リファクタリング (refactor)
- [ ] ドキュメント (docs)
- [ ] その他 (chore)

## 変更内容
### 何を変更したか
[簡潔な説明]

### なぜ変更したか
[背景・理由]

### どのように変更したか
- [変更点1]
- [変更点2]

## テスト
### 実施したテスト
- [ ] ユニットテスト追加
- [ ] 統合テスト追加
- [ ] 手動テスト実施

### テスト結果
[テスト結果の説明]

## 関連Issue
Closes #[番号]
Refs #[番号]

## レビューポイント
[レビュアーに特に見てほしい点]
```

## テスト戦略

### テストピラミッド

```
       /\
      /E2E\       少 (遅い、高コスト)
     /------\
    / 統合   \     中
   /----------\
  / ユニット   \   多 (速い、低コスト)
 /--------------\
```

**目標比率**:
- ユニットテスト: 70%
- 統合テスト: 20%
- E2Eテスト: 10%

### テストの書き方

**Given-When-Then パターン**:

```java
class MatrixServiceTest {

    @Nested
    @DisplayName("行列の生成")
    class CreateMatrix {

        @Test
        @DisplayName("正常なデータの場合、行列を生成できる")
        void shouldCreateMatrixWithValidData() {
            // Given: 準備
            MatrixRepository mockRepository = mock(MatrixRepository.class);
            MatrixService service = new MatrixService(mockRepository);
            double[][] validData = {{1, 2}, {3, 4}};

            // When: 実行
            Matrix result = service.create(validData);

            // Then: 検証
            assertNotNull(result.getId());
            assertArrayEquals(validData, result.getData());
        }

        @Test
        @DisplayName("不正な次元の場合、IllegalArgumentExceptionをスローする")
        void shouldThrowExceptionForInvalidDimensions() {
            // Given: 準備
            MatrixRepository mockRepository = mock(MatrixRepository.class);
            MatrixService service = new MatrixService(mockRepository);
            double[][] invalidData = {{1, 2}, {3}};

            // When/Then: 実行と検証
            assertThrows(IllegalArgumentException.class, () ->
                service.create(invalidData)
            );
        }
    }
}
```

### カバレッジ目標

**測定可能な目標**:

```groovy
// build.gradle - JaCoCo設定
plugins {
    id 'jacoco'
}

jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                counter = 'LINE'
                minimum = 0.80
            }
            limit {
                counter = 'BRANCH'
                minimum = 0.80
            }
        }
        rule {
            includes = ['com.linalgpad.service.*']
            limit {
                counter = 'LINE'
                minimum = 0.90
            }
            limit {
                counter = 'BRANCH'
                minimum = 0.90
            }
        }
    }
}
```

**理由**:
- 重要なビジネスロジック(service/)は高いカバレッジを要求
- UI層(JavaFX Controller等)は低めでも許容
- 100%を目指さない (コストと効果のバランス)

## コードレビュープロセス

### レビューの目的

1. **品質保証**: バグの早期発見
2. **知識共有**: チーム全体でコードベースを理解
3. **学習機会**: ベストプラクティスの共有

### 効果的なレビューのポイント

**レビュアー向け**:

1. **建設的なフィードバック**
```markdown
## ❌ 悪い例
このコードはダメです。

## ✅ 良い例
この実装だと O(n²) の時間計算量になります。
Map を使うと O(n) に改善できます:

```java
Map<String, Matrix> matrixMap = matrices.stream()
    .collect(Collectors.toMap(Matrix::getId, Function.identity()));
List<Matrix> result = ids.stream()
    .map(matrixMap::get)
    .collect(Collectors.toList());
```
```

2. **優先度の明示**
```markdown
[必須] セキュリティ: パスワードがログに出力されています
[推奨] パフォーマンス: ループ内でのDB呼び出しを避けましょう
[提案] 可読性: このメソッド名をもっと明確にできませんか？
[質問] この処理の意図を教えてください
```

3. **ポジティブなフィードバックも**
```markdown
✨ この実装は分かりやすいですね！
👍 エッジケースがしっかり考慮されています
💡 このパターンは他でも使えそうです
```

**レビュイー向け**:

1. **セルフレビューを実施**
   - PR作成前に自分でコードを見直す
   - 説明が必要な箇所にコメントを追加

2. **小さなPRを心がける**
   - 1PR = 1機能
   - 変更ファイル数: 10ファイル以内を推奨
   - 変更行数: 300行以内を推奨

3. **説明を丁寧に**
   - なぜこの実装にしたか
   - 検討した代替案
   - 特に見てほしいポイント

### レビュー時間の目安

- 小規模PR (100行以下): 15分
- 中規模PR (100-300行): 30分
- 大規模PR (300行以上): 1時間以上

**原則**: 大規模PRは避け、分割する

## 自動化の推進（該当する場合）

### 品質チェックの自動化

**自動化項目と採用ツール**:

1. **静的解析**
   - **Checkstyle**
     - Javaのコーディング規約を自動チェック
     - Google Java Styleなど標準ルールセットを適用可能
     - 設定ファイル: `config/checkstyle/checkstyle.xml`
   - **SpotBugs**
     - バイトコード解析による潜在的バグの自動検出
     - NullPointerExceptionやリソースリークなどを事前に発見
     - Gradleプラグインで容易に導入

2. **コードフォーマット**
   - **google-java-format** (任意)
     - Google Java Styleに基づく自動整形
     - IDE連携またはGradleタスクで適用
     - レビュー時のスタイル議論を削減

3. **コンパイルチェック**
   - **javac (Gradle compileJavaタスク)**
     - Java 17+の型チェックとコンパイルエラー検出
     - `-Xlint:all`オプションで警告を網羅的に検出
     - 設定ファイル: `build.gradle`

4. **テスト実行**
   - **JUnit 5**
     - Java標準のテスティングフレームワーク
     - `@Nested`によるテスト構造化、`@DisplayName`による日本語テスト名
     - JaCoCoによるカバレッジ測定を組み合わせて使用
     - Gradleの`test`タスクで実行

5. **ビルド確認**
   - **Gradle**
     - `./gradlew build`で コンパイル・テスト・静的解析を一括実行
     - `build.gradle`で依存関係とビルド設定を一元管理
     - JavaFXプラグインでGUIアプリのパッケージングにも対応

**実装方法**:

**1. CI/CD (GitHub Actions)**
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'
      - uses: gradle/actions/setup-gradle@v4
      - run: ./gradlew check
      - run: ./gradlew build
```

**2. Pre-commit フック (Gradle タスク + Git フック)**
```groovy
// build.gradle
plugins {
    id 'java'
    id 'application'
    id 'checkstyle'
    id 'jacoco'
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
}

tasks.named('test') {
    useJUnitPlatform()
    finalizedBy jacocoTestReport
}

checkstyle {
    toolVersion = '10.12.5'
    configFile = file("config/checkstyle/checkstyle.xml")
}

// Pre-commitフック登録タスク
tasks.register('installGitHooks', Copy) {
    from 'scripts/pre-commit'
    into '.git/hooks'
    fileMode 0755
}
```
```bash
# scripts/pre-commit
#!/bin/bash
./gradlew check
```

**導入効果**:
- コミット前に自動チェックが走り、不具合コードの混入を防止
- PR作成時に自動でCI実行され、マージ前に品質を担保
- 早期発見により、修正コストを最大80%削減（バグ検出が本番後の場合と比較）

**この構成を選んだ理由**:
- Java 17+エコシステムにおける標準的かつ安定した構成
- Gradleによりビルド・テスト・静的解析を統一的に管理
- JUnit 5とJaCoCoの組み合わせにより、テストとカバレッジ測定がシームレスに連携

## チェックリスト

- [ ] ブランチ戦略が決まっている
- [ ] コミットメッセージ規約が明確である
- [ ] PRテンプレートが用意されている
- [ ] テストの種類とカバレッジ目標が設定されている
- [ ] コードレビュープロセスが定義されている
- [ ] CI/CDパイプラインが構築されている
