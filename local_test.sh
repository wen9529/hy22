#!/bin/bash
set -e

echo "==================================================="
echo "正在执行本地节点转换与测试..."
echo "==================================================="

python3 -m pip install requests pyyaml
python3 scripts/convert.py

echo "==================================================="
echo "执行完毕！已生成 config.yaml, hy2_config.yaml, hy2_links.txt 等文件。"
echo "==================================================="
