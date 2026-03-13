.PHONY: test lint package clean

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
		README.txt \
		input/.gitkeep \
		output/.gitkeep
	@echo "生成完了: dist/grep_analyzer.zip"

# クリーンアップ
clean:
	rm -rf dist/ __pycache__/ .venv/ htmlcov/ .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
