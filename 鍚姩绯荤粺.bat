@echo off
chcp 65001 >nul
cd /d "%~dp0\web_app"
call "%~dp0web_app\启动系统.bat"
