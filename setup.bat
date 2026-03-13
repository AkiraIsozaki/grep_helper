@echo off
REM grep結果自動分類ツール セットアップスクリプト（Windows）
REM Python 3.12以上が必要です。

SET SCRIPT_DIR=%~dp0

echo セットアップを開始します...

REM Python バージョン確認
python -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)" 2>nul
IF ERRORLEVEL 1 (
    echo エラー: Python 3.12以上が見つかりません。インストールしてください。 1>&2
    exit /b 1
)

REM venv 作成
python -m venv "%SCRIPT_DIR%.venv"
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM 依存ライブラリのインストール
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet

echo セットアップ完了。
echo 実行方法: run.bat --source-dir C:\path\to\javaproject
