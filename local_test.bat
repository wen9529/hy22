@echo off
chcp 65001 >nul
title 本地节点提取与测试脚本
echo ===================================================
echo 正在执行本地节点转换与测试...
echo ===================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3 并添加到 PATH 环境变量。
    pause
    exit /b 1
)

pip install requests pyyaml
python scripts\convert.py

echo.
echo ===================================================
echo 执行完毕！请检查生成的文件：
echo - config.yaml / clash.yaml
echo - singbox.json
echo - xray_config.json
echo - xray_links.txt / sub.txt
echo ===================================================
pause
