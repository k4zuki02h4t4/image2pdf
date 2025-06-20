@echo off
:: Image2PDF ビルドスクリプト
:: Windows 11対応の実行可能ファイルを作成

echo ========================================
echo Image2PDF ビルドスクリプト v1.0.0
echo Windows 11対応画像→PDF変換ツール
echo ========================================
echo.

:: 管理者権限チェック（オプション）
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] 管理者権限で実行中
) else (
    echo [WARN] 管理者権限が推奨されています
)

:: Pythonの存在確認
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Pythonが見つかりません
    echo Pythonをインストールしてからビルドを実行してください
    pause
    exit /b 1
)

echo [INFO] Python: 
python --version

:: 仮想環境の確認・作成
if not exist "venv" (
    echo [INFO] 仮想環境を作成中...
    python -m venv venv
    if %errorLevel% neq 0 (
        echo [ERROR] 仮想環境の作成に失敗しました
        pause
        exit /b 1
    )
)

:: 仮想環境のアクティベート
echo [INFO] 仮想環境をアクティベート中...
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo [ERROR] 仮想環境のアクティベートに失敗しました
    pause
    exit /b 1
)

:: 依存関係のインストール
echo [INFO] 依存関係をインストール中...
pip install --upgrade pip
pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo [ERROR] 依存関係のインストールに失敗しました
    pause
    exit /b 1
)

:: PyInstallerのインストール（ビルド用）
echo [INFO] PyInstallerをインストール中...
pip install pyinstaller
if %errorLevel% neq 0 (
    echo [ERROR] PyInstallerのインストールに失敗しました
    pause
    exit /b 1
)

:: テストの実行（オプション）
set /p run_tests="テストを実行しますか？ (y/N): "
if /i "%run_tests%"=="y" (
    echo [INFO] テストを実行中...
    pytest tests/ -v
    if %errorLevel% neq 0 (
        echo [WARN] テストが失敗しましたが、ビルドを続行します
        echo 詳細はテスト結果を確認してください
        pause
    )
)

:: リソースディレクトリの確認・作成
if not exist "resources\icons" (
    echo [INFO] リソースディレクトリを作成中...
    mkdir "resources\icons"
    mkdir "resources\styles"
    
    echo [WARN] アイコンファイルが見つかりません
    echo resources\icons\app_icon.ico を配置してください
    echo とりあえずダミーファイルを作成します...
    
    :: ダミーアイコンファイル作成（実際のプロジェクトでは適切なアイコンを配置）
    echo. > "resources\icons\app_icon.ico"
)

:: ビルド前のクリーンアップ
echo [INFO] 前回のビルドファイルをクリーンアップ中...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del "*.spec"
if exist "version_info.txt" del "version_info.txt"

:: PyInstallerでビルド実行
echo [INFO] PyInstallerでビルド実行中...
echo これには数分かかる場合があります...
pyinstaller build.spec --clean --noconfirm
if %errorLevel% neq 0 (
    echo [ERROR] ビルドに失敗しました
    echo build.specの設定を確認してください
    pause
    exit /b 1
)

:: ビルド結果の確認
if exist "dist\Image2PDF.exe" (
    echo.
    echo ========================================
    echo [SUCCESS] ビルド完了！
    echo ========================================
    echo.
    echo 実行ファイル: dist\Image2PDF.exe
    
    :: ファイルサイズを表示
    for %%A in ("dist\Image2PDF.exe") do (
        set size=%%~zA
        set /a sizeMB=!size!/1024/1024
        echo ファイルサイズ: !sizeMB! MB
    )
    
    echo.
    echo [INFO] テスト実行してみますか？
    set /p test_run="テスト実行 (y/N): "
    if /i "!test_run!"=="y" (
        echo [INFO] テスト実行中...
        start "" "dist\Image2PDF.exe"
    )
    
) else (
    echo [ERROR] 実行ファイルが作成されませんでした
    echo dist\Image2PDF.exe が見つかりません
    exit /b 1
)

:: インストーラー作成の提案
echo.
echo [INFO] Windowsインストーラーを作成しますか？
echo NSIS (Nullsoft Scriptable Install System) が必要です
set /p create_installer="インストーラー作成 (y/N): "
if /i "%create_installer%"=="y" (
    if exist "installer.nsi" (
        echo [INFO] NSISでインストーラーを作成中...
        makensis installer.nsi
        if %errorLevel% eq 0 (
            echo [SUCCESS] インストーラーが作成されました
        ) else (
            echo [ERROR] インストーラーの作成に失敗しました
            echo NSISがインストールされているか確認してください
        )
    ) else (
        echo [WARN] installer.nsi が見つかりません
        echo インストーラー作成スクリプトを作成してください
    )
)

:: 署名の提案（コード署名証明書がある場合）
echo.
echo [INFO] コード署名を行いますか？
echo 信頼できる発行者として認識されるためには証明書が必要です
set /p sign_code="コード署名 (y/N): "
if /i "%sign_code%"=="y" (
    echo [INFO] コード署名を実行してください
    echo signtool sign /fd SHA256 /t http://timestamp.digicert.com "dist\Image2PDF.exe"
    echo 詳細はMicrosoftのドキュメントを参照してください
)

echo.
echo ========================================
echo ビルド処理が完了しました
echo.
echo 出力ファイル:
echo   - dist\Image2PDF.exe (実行ファイル)
echo   - build\ (ビルド一時ファイル)
echo.
echo 配布の際は dist\Image2PDF.exe を使用してください
echo ========================================

pause
