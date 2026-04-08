.PHONY: test lint package clean download-wheels download-python-src package-solaris

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

# Python 3.7 ソースtarballをダウンロード（インターネット接続環境で実行）
# GitHub経由で取得（python.orgが遮断されている環境向け）
download-python-src:
	mkdir -p python-src
	curl -L -o python-src/Python-3.7.17.tgz \
		https://github.com/python/cpython/archive/refs/tags/v3.7.17.tar.gz || \
	wget -O python-src/Python-3.7.17.tgz \
		https://github.com/python/cpython/archive/refs/tags/v3.7.17.tar.gz
	@echo "Python 3.7.17 ソースを python-src/ にダウンロードしました。"

# Solaris向け配布zip生成（wheelhouse + Python ソース含む）
package-solaris: download-wheels download-python-src
	mkdir -p dist
	zip -r dist/grep_analyzer_solaris.zip \
		analyze.py \
		requirements.txt \
		setup_solaris.sh \
		run_solaris.sh \
		build_python_solaris.sh \
		README.md \
		wheelhouse/ \
		python-src/ \
		input/.gitkeep \
		output/.gitkeep
	@echo "生成完了: dist/grep_analyzer_solaris.zip"
