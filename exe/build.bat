@echo off
REM ComfyUI Workflow Unpacker - Build Script
REM 使用 PyInstaller 构建 EXE 文件

echo ========================================
echo ComfyUI Workflow Unpacker - Build Script
echo ========================================
echo.

REM 检查程序是否正在运行
tasklist /FI "IMAGENAME eq comfy-pack-unpack.exe" 2>NUL | find /I /N "comfy-pack-unpack.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Warning: comfy-pack-unpack.exe is currently running
    echo Please close it before continuing...
    echo.
    pause
)

REM 检查是否在 exe 目录
if not exist unpacker.spec (
    echo Error: Please run this script from the exe directory
    pause
    exit /b 1
)

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM 检查是否安装了依赖
echo Checking dependencies...
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM 清理旧的构建文件
echo Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist comfy-pack-unpack.exe del /q comfy-pack-unpack.exe

REM 构建 EXE
echo.
echo Building EXE file...
echo This may take several minutes...
echo.
pyinstaller --clean unpacker.spec

if errorlevel 1 (
    echo.
    echo Error: Build failed!
    pause
    exit /b 1
)

REM 复制 EXE 到当前目录
if exist dist\comfy-pack-unpack.exe (
    REM 尝试复制，如果失败则提示
    copy /Y dist\comfy-pack-unpack.exe comfy-pack-unpack.exe >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ========================================
        echo Warning: Cannot overwrite existing EXE
        echo The file may be in use. Please close it.
        echo ========================================
        echo.
        echo Press any key to retry, or Ctrl+C to cancel...
        pause >nul
        copy /Y dist\comfy-pack-unpack.exe comfy-pack-unpack.exe
    )
    
    echo.
    echo ========================================
    echo Build completed successfully!
    echo ========================================
    echo.
    echo EXE file location: exe\comfy-pack-unpack.exe
    echo File size: 
    dir comfy-pack-unpack.exe | findstr "comfy-pack-unpack.exe"
    echo.
    echo Note: Only one EXE file is kept - always use comfy-pack-unpack.exe
    echo.
) else (
    echo.
    echo Error: EXE file not found in dist folder
    pause
    exit /b 1
)

pause

