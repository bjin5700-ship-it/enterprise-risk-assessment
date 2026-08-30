@echo off
chcp 65001 >nul
title 企业风险动态评估系统
cd /d "%~dp0"
set ERM_PORT=8088
set ERM_HOST=0.0.0.0

echo.
echo ============================================================
echo   企业风险动态评估系统
echo   启动后访问: http://127.0.0.1:%ERM_PORT%
echo ============================================================
echo.

where py >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

py -3 -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装依赖，请稍候...
    py -3 -m pip install flask openpyxl python-docx reportlab jinja2 werkzeug
)

echo 正在启动服务，浏览器将自动打开...
echo 请勿关闭本黑色窗口！关闭后网页将无法访问。
echo.

REM 释放端口，避免旧进程导致 API 版本不一致
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %ERM_PORT% -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul

py -3 app.py

echo.
echo 服务已停止。
pause
