@echo off
REM grep結果自動分類ツール 実行スクリプト（Windows）
REM 使い方: run.bat --source-dir C:\path\to\javaproject [--input-dir input] [--output-dir output]

SET SCRIPT_DIR=%~dp0

IF NOT EXIST "%SCRIPT_DIR%.venv" (
    echo エラー: .venv が見つかりません。先に setup.bat を実行してください。 1>&2
    exit /b 1
)

call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
python "%SCRIPT_DIR%analyze.py" %*
