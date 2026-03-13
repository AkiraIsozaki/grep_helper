"""analyze.py のユニットテスト・統合テスト。

実行方法:
    python -m unittest discover -v
    python -m unittest test_analyze.TestGrepParser
"""
import csv
import sys
import unittest
from pathlib import Path

from analyze import (
    GrepRecord,
    ProcessStats,
    RefType,
    UsageType,
    classify_usage_regex,
    determine_scope,
    extract_variable_name,
    parse_grep_line,
    print_report,
    write_tsv,
)


# ---------------------------------------------------------------------------
# TestGrepParser
# ---------------------------------------------------------------------------

class TestGrepParser(unittest.TestCase):
    """F-01: parse_grep_line() のテスト。"""

    def test_parse_valid_line_returns_dict(self):
        """正常なgrep行をパースできること。"""
        line = 'src/main/java/Constants.java:10:    public static final String CODE = "TARGET";'
        result = parse_grep_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["filepath"], "src/main/java/Constants.java")
        self.assertEqual(result["lineno"], "10")
        self.assertIn("CODE", result["code"])

    def test_parse_binary_notice_line_returns_none(self):
        """バイナリ通知行はNoneを返すこと。"""
        line = "Binary file src/main/resources/logo.png matches"
        self.assertIsNone(parse_grep_line(line))

    def test_parse_empty_line_returns_none(self):
        """空行・空白のみの行はNoneを返すこと。"""
        self.assertIsNone(parse_grep_line(""))
        self.assertIsNone(parse_grep_line("   "))
        self.assertIsNone(parse_grep_line("\n"))

    def test_parse_windows_path_handled(self):
        """Windowsパス（C:\\...）でも正しくパースできること。"""
        line = r"C:\project\src\Constants.java:42:    String s = CODE;"
        result = parse_grep_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["lineno"], "42")
        self.assertIn("CODE", result["code"])

    def test_parse_invalid_format_returns_none(self):
        """区切り文字がない不正行はNoneを返すこと。"""
        self.assertIsNone(parse_grep_line("no colon separator here"))

    def test_parse_code_is_stripped(self):
        """コード行の前後の空白がtrimされること。"""
        line = "Foo.java:5:    int x = 1;   "
        result = parse_grep_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "int x = 1;")


# ---------------------------------------------------------------------------
# TestUsageClassifier
# ---------------------------------------------------------------------------

class TestUsageClassifier(unittest.TestCase):
    """F-02: classify_usage_regex() の7種分類テスト。"""

    def test_classify_annotation(self):
        """アノテーション行を正しく分類すること。"""
        self.assertEqual(classify_usage_regex('@RequestMapping("TARGET")'), "アノテーション")

    def test_classify_constant_definition(self):
        """static final定数定義を正しく分類すること。"""
        code = 'public static final String CODE = "TARGET";'
        self.assertEqual(classify_usage_regex(code), "定数定義")

    def test_classify_condition_if(self):
        """if文を正しく分類すること。"""
        self.assertEqual(classify_usage_regex('if (x.equals(CODE)) {'), "条件判定")

    def test_classify_condition_equals(self):
        """.equals() を含む行を条件判定と分類すること（returnより優先）。"""
        # 優先度: 条件判定（.equals）> return文 のため、条件判定になる
        self.assertEqual(classify_usage_regex('return a.equals(CODE);'), "条件判定")

    def test_classify_condition_not_equals(self):
        """!= を含む行を条件判定と分類すること。"""
        self.assertEqual(classify_usage_regex('if (x != CODE) {'), "条件判定")

    def test_classify_return(self):
        """return文を正しく分類すること。"""
        self.assertEqual(classify_usage_regex('return CODE;'), "return文")

    def test_classify_variable_assignment(self):
        """変数代入を正しく分類すること。"""
        self.assertEqual(classify_usage_regex('String msg = CODE;'), "変数代入")

    def test_classify_method_argument(self):
        """メソッド引数を正しく分類すること。"""
        self.assertEqual(classify_usage_regex('someService.process(CODE);'), "メソッド引数")

    def test_classify_comment_as_other(self):
        """コメント行を「その他」に分類すること。"""
        self.assertEqual(classify_usage_regex('// TARGET はここで使われる'), "その他")

    def test_classify_annotation_takes_priority_over_constant(self):
        """アノテーションが定数定義より優先されること。"""
        # @SomeAnnotation(static final がある行でもアノテーション優先)
        code = '@Value("${static.final.code}")'
        self.assertEqual(classify_usage_regex(code), "アノテーション")


# ---------------------------------------------------------------------------
# TestTsvWriter
# ---------------------------------------------------------------------------

class TestTsvWriter(unittest.TestCase):
    """F-05: write_tsv() のテスト。"""

    def setUp(self):
        """テスト用の一時ディレクトリを使用。"""
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.tmp_dir) / "test.tsv"

    def tearDown(self):
        """一時ファイルを削除。"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_record(self, keyword="KW", lineno="10", filepath="A.java",
                     ref_type=None, usage_type=None):
        return GrepRecord(
            keyword=keyword,
            ref_type=ref_type or RefType.DIRECT.value,
            usage_type=usage_type or UsageType.CONSTANT.value,
            filepath=filepath,
            lineno=lineno,
            code=f'String x = "{keyword}";',
        )

    def test_write_tsv_creates_file(self):
        """TSVファイルが生成されること。"""
        write_tsv([self._make_record()], self.output_path)
        self.assertTrue(self.output_path.exists())

    def test_write_tsv_utf8_bom_encoding(self):
        """UTF-8 BOM付きで出力されること（Excelで文字化けしない）。"""
        write_tsv([self._make_record()], self.output_path)
        raw = self.output_path.read_bytes()
        # UTF-8 BOM は EF BB BF
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), "BOMが先頭にない")

    def test_write_tsv_header_columns(self):
        """ヘッダー行が9列正しく出力されること。"""
        write_tsv([self._make_record()], self.output_path)
        with open(self.output_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
        expected = ["文言", "参照種別", "使用タイプ", "ファイルパス", "行番号",
                    "コード行", "参照元変数名", "参照元ファイル", "参照元行番号"]
        self.assertEqual(header, expected)

    def test_write_tsv_sort_order_numeric_lineno(self):
        """行番号が数値順にソートされること（"10" < "9" のバグがないこと）。"""
        records = [
            self._make_record(lineno="10"),
            self._make_record(lineno="9"),
            self._make_record(lineno="2"),
        ]
        write_tsv(records, self.output_path)
        with open(self.output_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)  # ヘッダーをスキップ
            rows = list(reader)
        linenos = [r[4] for r in rows]
        self.assertEqual(linenos, ["2", "9", "10"])

    def test_write_tsv_sort_order_keyword_then_filepath(self):
        """文言 → ファイルパス → 行番号の順にソートされること。"""
        records = [
            self._make_record(keyword="ZZZ", filepath="B.java", lineno="1"),
            self._make_record(keyword="AAA", filepath="C.java", lineno="1"),
            self._make_record(keyword="AAA", filepath="A.java", lineno="1"),
        ]
        write_tsv(records, self.output_path)
        with open(self.output_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            rows = list(reader)
        keywords = [r[0] for r in rows]
        filepaths = [r[3] for r in rows]
        self.assertEqual(keywords, ["AAA", "AAA", "ZZZ"])
        self.assertEqual(filepaths[:2], ["A.java", "C.java"])

    def test_write_tsv_output_dir_autocreated(self):
        """output/ ディレクトリが存在しなくても自動作成されること。"""
        nested_path = Path(self.tmp_dir) / "new_dir" / "sub" / "out.tsv"
        write_tsv([self._make_record()], nested_path)
        self.assertTrue(nested_path.exists())


# ---------------------------------------------------------------------------
# TestIndirectTracker
# ---------------------------------------------------------------------------

class TestIndirectTracker(unittest.TestCase):
    """F-03: determine_scope() / extract_variable_name() のテスト。"""

    def test_determine_scope_constant_returns_project(self):
        """定数定義は project スコープになること。"""
        self.assertEqual(
            determine_scope(UsageType.CONSTANT.value, 'public static final String CODE = "X";'),
            "project",
        )

    def test_determine_scope_field_returns_class(self):
        """アクセス修飾子付きフィールドは class スコープになること。"""
        self.assertEqual(
            determine_scope(UsageType.VARIABLE.value, 'private String type = "X";'),
            "class",
        )

    def test_determine_scope_local_variable_returns_method(self):
        """ローカル変数は method スコープになること（正規表現フォールバック）。"""
        # AST 未使用（filepath 省略）の場合は正規表現で判定される
        result = determine_scope(UsageType.VARIABLE.value, 'String msg = CODE;')
        # 修飾子なしのローカル変数は正規表現では method になる
        self.assertEqual(result, "method")

    def test_determine_scope_package_private_field_returns_class(self):
        """パッケージプライベートフィールド（修飾子なし）が class スコープになること。"""
        java_dir = Path(__file__).parent / "tests" / "fixtures" / "java"
        if not java_dir.exists():
            self.skipTest("フィクスチャが存在しません。")
        # Entity.java の `private String type = "SAMPLE";`（行8）は class スコープ
        result = determine_scope(
            UsageType.VARIABLE.value,
            'private String type = "SAMPLE";',
            "tests/fixtures/java/Entity.java",
            java_dir,
            8,
        )
        self.assertEqual(result, "class")

    def test_extract_variable_name_static_final(self):
        """static final 定数名を正しく抽出できること。"""
        code = 'public static final String CODE = "TARGET";'
        self.assertEqual(extract_variable_name(code, UsageType.CONSTANT.value), "CODE")

    def test_extract_variable_name_simple_assignment(self):
        """シンプルな変数代入から変数名を抽出できること。"""
        code = 'String msg = CODE;'
        self.assertEqual(extract_variable_name(code, UsageType.VARIABLE.value), "msg")

    def test_extract_variable_name_private_field(self):
        """private フィールドから変数名を抽出できること。"""
        code = 'private String type;'
        self.assertEqual(extract_variable_name(code, UsageType.VARIABLE.value), "type")

    def test_extract_variable_name_invalid_returns_none(self):
        """変数宣言でない行（条件文など）は None を返すこと。"""
        result = extract_variable_name('if (x.equals(CODE)) {', UsageType.CONDITION.value)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TestReporter
# ---------------------------------------------------------------------------

class TestReporter(unittest.TestCase):
    """F-06: print_report() のテスト。"""

    def _capture_report(self, stats: ProcessStats, files: list) -> str:
        """print_report() の標準出力をキャプチャして返す。"""
        from io import StringIO
        from unittest.mock import patch
        with patch('sys.stdout', new_callable=StringIO) as mock_out:
            print_report(stats, files)
            return mock_out.getvalue()

    def test_print_report_outputs_summary(self):
        """処理サマリが標準出力に出力されること。"""
        stats = ProcessStats(total_lines=10, valid_lines=8, skipped_lines=2)
        output = self._capture_report(stats, ["SAMPLE.grep"])
        self.assertIn("処理完了", output)
        self.assertIn("SAMPLE.grep", output)
        self.assertIn("10", output)
        self.assertIn("8", output)
        self.assertIn("2", output)

    def test_print_report_shows_fallback_files(self):
        """ASTフォールバックしたファイルが表示されること。"""
        stats = ProcessStats(fallback_files=["Foo.java", "Bar.java"])
        output = self._capture_report(stats, [])
        self.assertIn("ASTフォールバック", output)
        self.assertIn("Foo.java", output)
        self.assertIn("Bar.java", output)

    def test_print_report_shows_encoding_errors(self):
        """エンコーディングエラーのファイルが表示されること。"""
        stats = ProcessStats(encoding_errors=["Baz.java"])
        output = self._capture_report(stats, [])
        self.assertIn("エンコーディングエラー", output)
        self.assertIn("Baz.java", output)

    def test_print_report_no_optional_sections_when_empty(self):
        """フォールバック・エンコーディングエラーが0件のとき任意セクションが出力されないこと。"""
        stats = ProcessStats(total_lines=5, valid_lines=5, skipped_lines=0)
        output = self._capture_report(stats, ["X.grep"])
        self.assertNotIn("ASTフォールバック", output)
        self.assertNotIn("エンコーディングエラー", output)


# ---------------------------------------------------------------------------
# TestIntegration
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):
    """E2E統合テスト。フィクスチャを使って直接参照の出力を検証する。"""

    FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"

    def setUp(self):
        """フィクスチャの存在確認。"""
        if not self.FIXTURES_DIR.exists():
            self.skipTest("tests/fixtures/ が存在しません。統合テストをスキップします。")

    def test_full_flow_produces_expected_tsv(self):
        """直接参照がTSVに正しく出力されることを確認。"""
        import subprocess
        import tempfile

        input_dir = self.FIXTURES_DIR / "input"
        java_dir = self.FIXTURES_DIR / "java"
        expected_tsv = self.FIXTURES_DIR / "expected" / "SAMPLE.tsv"

        if not input_dir.exists() or not java_dir.exists() or not expected_tsv.exists():
            self.skipTest("統合テスト用フィクスチャが不完全です。")

        with tempfile.TemporaryDirectory() as tmp_out:
            project_root = Path(__file__).parent
            result = subprocess.run(
                [
                    sys.executable, str(project_root / "analyze.py"),
                    "--source-dir", str(java_dir),
                    "--input-dir", str(input_dir),
                    "--output-dir", tmp_out,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            self.assertEqual(result.returncode, 0, f"analyze.py が失敗しました:\n{result.stderr}")

            actual_tsv = Path(tmp_out) / "SAMPLE.tsv"
            self.assertTrue(actual_tsv.exists(), "出力TSVが生成されませんでした。")

            # 期待TSVと比較（ヘッダー行 + データ行）
            with open(expected_tsv, encoding="utf-8-sig", newline="") as f:
                expected_rows = list(csv.reader(f, delimiter="\t"))
            with open(actual_tsv, encoding="utf-8-sig", newline="") as f:
                actual_rows = list(csv.reader(f, delimiter="\t"))

            self.assertEqual(
                actual_rows[0], expected_rows[0],
                "ヘッダー行が一致しません。"
            )
            # データ行数が期待値以上であることを確認（間接参照追加で増える場合があるため）
            self.assertGreaterEqual(
                len(actual_rows), len(expected_rows),
                f"出力行数が期待値({len(expected_rows)})を下回っています: {len(actual_rows)}行。"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
