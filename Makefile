.PHONY: test lint package clean download-wheels package-solaris

# 全ユニットテスト実行
test:
	python -m unittest discover -v

# コードスタイルチェック
lint:
	python -m flake8 analyze.py test_analyze.py

# 配布用 zip 生成
package:
	mkdir -p dist
	zip -r dist/grep_analyzer.zip \
		analyze.py \
		test_analyze.py \
		requirements.txt \
		setup.sh \
		setup.bat \
		run.sh \
		run.bat \
		README.md \
		input/.gitkeep \
		output/.gitkeep
	@echo "生成完了: dist/grep_analyzer.zip"

# クリーンアップ
clean:
	rm -rf dist/ __pycache__/ .venv/ htmlcov/ .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

# ----------------------------------------------------------------
# Solaris 10 SPARC / オフライン環境向け
# ----------------------------------------------------------------

# 依存wheelをダウンロード（インターネット接続環境で実行）
# javalangは純粋Pythonパッケージのため、Linux で取得したwheelをSPARCでも使用可能
download-wheels:
	mkdir -p wheelhouse
	pip download -r requirements.txt -d wheelhouse
	@echo "wheelhouse/ にwheelファイルをダウンロードしました。"
	@echo "wheelhouse/ ディレクトリごとSolaris環境に持ち込んでください。"

# Solaris向け配布zip生成（wheelhouse含む）
package-solaris: download-wheels
	mkdir -p dist
	zip -r dist/grep_analyzer_solaris.zip \
		analyze.py \
		requirements.txt \
		setup_solaris.sh \
		run_solaris.sh \
		README.md \
		wheelhouse/ \
		input/.gitkeep \
		output/.gitkeep
	@echo "生成完了: dist/grep_analyzer_solaris.zip"
