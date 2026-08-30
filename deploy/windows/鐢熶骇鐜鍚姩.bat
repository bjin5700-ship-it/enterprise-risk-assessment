@echo off
chcp 65001 >nul
title 企业风险动态评估系统 - 生产环境
cd /d "%~dp0\.."
cd web_app

REM ========== 请按实际服务器修改 ==========
set ERM_ENV=production
set ERM_HOST=0.0.0.0
set ERM_PORT=8088
set ERM_THREADS=8
REM 客户访问地址，例如 https://erm.example.com
set ERM_PUBLIC_URL=https://请改为您的域名
REM 生产密钥（请改为随机字符串）
set ERM_SECRET_KEY=请改为随机密钥
REM ========================================

where py >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python 3
    pause & exit /b 1
)

py -3 -c "import waitress" >nul 2>&1
if %errorlevel% neq 0 (
    echo 安装生产依赖...
    py -3 -m pip install -r ..\requirements.txt
)

echo.
echo ============================================================
echo   生产模式启动 (Waitress)
echo   公网地址: %ERM_PUBLIC_URL%
echo   内网监听: %ERM_HOST%:%ERM_PORT%
echo   请配合防火墙/Nginx 将 80/443 转发到此端口
echo ============================================================
echo.

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %ERM_PORT% -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul

py -3 run_production.py

pause
