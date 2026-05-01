@echo off
chcp 65001 >nul
echo ==============================
echo   GeoQuery PyInstaller 打包
echo ==============================
echo.

echo [1/2] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖安装失败！
    pause
    exit /b 1
)
echo 依赖安装完成
echo.

echo [2/2] 开始打包...
pyinstaller --noconfirm --onedir --console --name "GeoQuery" --add-data "templates;templates" --clean app.py
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo ==============================
echo   打包完成！
echo   输出目录: dist\GeoQuery\
echo   运行文件: dist\GeoQuery\GeoQuery.exe
echo ==============================
echo.
echo 提示: 将 dist\GeoQuery 整个文件夹复制给使用者即可
echo       使用者双击 GeoQuery.exe 运行，浏览器会自动打开
pause
