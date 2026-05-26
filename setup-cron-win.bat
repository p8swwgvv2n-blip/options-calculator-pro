@echo off
REM 期权 IV 定时导出 — Windows 安装脚本
REM 运行此脚本后，每天 9:00 自动导出 IV 数据
REM
REM 用法：双击 setup-cron-win.bat 运行（需要管理员权限）

set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%定时导出期权IV.py

REM Check Python exists
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where python3 >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo 错误: 未找到 python 或 python3，请先安装 Python
        pause
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

REM Create scheduled task (run daily at 9:00 AM)
echo 正在创建定时任务...
schtasks /create /tn "期权IV数据导出" /tr "\"%PYTHON_CMD%\" \"%PYTHON_SCRIPT%\"" /sc daily /st 09:00 /ru SYSTEM
if %ERRORLEVEL% EQU 0 (
    echo 定时任务已创建：每天 9:00 自动导出
) else (
    echo 创建失败，请以管理员身份运行此脚本
    pause
    exit /b 1
)

REM Run once to test
echo.
echo 运行一次测试...
%PYTHON_CMD% "%PYTHON_SCRIPT%"

echo.
echo 安装完成！
echo 查看任务: schtasks /query /tn "期权IV数据导出"
echo 删除任务: schtasks /delete /tn "期权IV数据导出" /f
pause
