import { WorkflowOptions } from '../types';

export function generateWorkflowYaml(opts: WorkflowOptions): string {
  return `name: ${opts.workflowName || '自动提取节点并生成 Clash 订阅'}

on:
  schedule:
    # 按照设定时间定时运行 (UTC 时间)
    - cron: '${opts.cronSchedule || '0 */6 * * *'}'
  workflow_dispatch: # 支持在 GitHub 仓库 Actions 页面手动点击运行
    inputs:
      force_update:
        description: '强制更新并提交 (即使节点无变化)'
        required: false
        type: boolean
        default: false
  push:
    paths:
      - 'urls.txt'
      - 'template.yaml'
      - 'scripts/**'

# 并发控制：避免多次提交冲突
concurrency:
  group: \${{ github.workflow }}-\${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: write # 必须赋予写入权限以提交生成的订阅文件

jobs:
  update-nodes:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: 检出仓库代码 (Checkout Repository)
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: 安装 Python 运行环境 (Setup Python)
        uses: actions/setup-python@v5
        with:
          python-version: '${opts.pythonVersion || '3.11'}'
          cache: 'pip'

      - name: 安装依赖 (Install Dependencies)
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            pip install requests pyyaml
          fi

      - name: 执行节点提取与转换 (Extract & Convert Nodes)
        env:
          FORCE_UPDATE: \${{ github.event.inputs.force_update || 'false' }}
        run: |
          python scripts/convert.py

      - name: 检查并提交生成的文件 (Commit and Push)
        run: |
          git config --local user.name "github-actions[bot]"
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          
          # 检查是否有变更
          CHANGED_FILES=""
          if [[ -n $(git status -s ${opts.targetFileName || 'clash.yaml'}) ]]; then
            CHANGED_FILES="$CHANGED_FILES ${opts.targetFileName || 'clash.yaml'}"
          fi
          if [[ -f singbox.json && -n $(git status -s singbox.json) ]]; then
            CHANGED_FILES="$CHANGED_FILES singbox.json"
          fi
          if [[ -f sub.txt && -n $(git status -s sub.txt) ]]; then
            CHANGED_FILES="$CHANGED_FILES sub.txt"
          fi
          
          if [[ -n "$CHANGED_FILES" || "\${{ github.event.inputs.force_update }}" == "true" ]]; then
            echo "检测到文件变更: $CHANGED_FILES，正在提交..."
            git add ${opts.targetFileName || 'clash.yaml'}
            git add singbox.json sub.txt 2>/dev/null || true
            git commit -m "${opts.commitMessage || 'chore(cron): 自动更新节点配置 [skip ci]'}"
            git pull --rebase origin ${opts.branchName || 'main'} || true
            git push origin ${opts.branchName || 'main'}
            echo "提交成功！"
          else
            echo "节点配置与输出文件无变动，跳过提交。"
          fi
`;
}

export function generatePythonScript(opts: {
  targetFileName: string;
  includeSingBox: boolean;
}): string {
  return `#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化脚本：
1. 从 urls.txt 或 bat 文本提取节点 URL (智能识别主用与备用镜像)
2. 批量并发请求 URL 下载 Hysteria 2 节点 JSON 配置文件
3. 按照 template.yaml 模板渲染并生成 Clash Meta (Mihomo) 订阅文件
4. 同步输出 singbox.json 和 Base64 订阅 sub.txt
5. 向 GitHub Actions Job Summary 写入富文本状态报表
"""

import os
import re
import sys
import json
import base64
import datetime
from urllib.parse import quote
import warnings

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("[!] 正在安装 requests 库...")
    os.system("pip install requests")
    import requests

try:
    import yaml
except ImportError:
    print("[!] 正在安装 pyyaml 库...")
    os.system("pip install pyyaml")
    import yaml

# 配置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.yaml")
CLASH_OUTPUT = os.path.join(BASE_DIR, "${opts.targetFileName || 'clash.yaml'}")
SINGBOX_OUTPUT = os.path.join(BASE_DIR, "singbox.json")
BASE64_OUTPUT = os.path.join(BASE_DIR, "sub.txt")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT = 12  # 单个请求超时时间 (秒)
MAX_RETRIES = 2

def extract_node_items_from_file(file_path):
    """
    从文本文件中提取 URL 并自动匹配主用与备用镜像
    支持：
    1. 批处理脚本中的 wget 链接
    2. 纯文本每行一个 URL
    3. 自动识别编号路径如 /hysteria2/1/config.json 并组合备用镜像
    """
    if not os.path.exists(file_path):
        print(f"[错误] 未找到节点输入文件: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 提取所有 HTTP/HTTPS URL
    urls = re.findall(r"https?://[^\\s\"'<>]+", content)
    cleaned_urls = [u.rstrip('",\\').strip() for u in urls if u.strip()]

    node_groups = {}
    unkeyed_urls = []

    for url in cleaned_urls:
        # 匹配 /hysteria2/(\\d+)/ 或 /(\\d+)/config.json 结构
        match = re.search(r"/hysteria2/(\\d+)/", url, re.I) or re.search(r"/(\\d+)/config\\.json", url, re.I)
        if match:
            idx = int(match.group(1))
            key = f"node_{idx}"
            if key not in node_groups:
                node_groups[key] = {"index": idx, "primary": url, "fallback": None}
            elif not node_groups[key]["fallback"] and node_groups[key]["primary"] != url:
                node_groups[key]["fallback"] = url
        else:
            if url not in unkeyed_urls:
                unkeyed_urls.append(url)

    items = []
    # 按照节点编号升序排序
    for key, val in sorted(node_groups.items(), key=lambda x: x[1]["index"]):
        items.append({
            "name": f"Hysteria2-{val['index']:02d}",
            "primary": val["primary"],
            "fallback": val["fallback"]
        })

    # 追加未匹配到编号的独立 URL
    for i, url in enumerate(unkeyed_urls, start=len(items) + 1):
        items.append({
            "name": f"Node-{i:02d}",
            "primary": url,
            "fallback": None
        })

    print(f"[*] 成功解析识别 {len(items)} 个节点任务 (含备用镜像通道)")
    return items

def fetch_json_with_fallback(primary_url, fallback_url=None):
    """
    请求 JSON 节点配置，主 URL 失败或超时自动尝试备用镜像，支持重试与 SSL 容错
    """
    urls_to_try = [u for u in [primary_url, fallback_url] if u]
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Connection": "close"
    }

    for idx, target_url in enumerate(urls_to_try):
        is_mirror = (idx > 0)
        mirror_tag = " [备用镜像]" if is_mirror else " [主线路]"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    target_url,
                    headers=headers,
                    timeout=TIMEOUT,
                    verify=False  # 避免因镜像站自签名证书或未配置CA报错
                )
                if resp.status_code == 200:
                    text_content = resp.text.strip()
                    try:
                        data = json.loads(text_content)
                        print(f"  [+] 下载成功{mirror_tag}: {target_url}")
                        return {
                            "data": data,
                            "active_url": target_url,
                            "is_mirror": is_mirror
                        }
                    except json.JSONDecodeError:
                        print(f"  [-] 返回内容非合法 JSON: {target_url}")
                else:
                    print(f"  [-] HTTP {resp.status_code}{mirror_tag}: {target_url}")
            except Exception as e:
                err_msg = str(e)
                if "timeout" in err_msg.lower():
                    err_msg = "请求超时"
                print(f"  [-] 连接失败 (第 {attempt} 次){mirror_tag}: {err_msg}")

    return None

def convert_to_clash_proxy(raw_json, node_name):
    """
    将 Hysteria 2 客户端 config.json 转换为 Clash Meta (Mihomo) 节点字典
    兼容多种 JSON 格式与字段写法
    """
    if not raw_json or not isinstance(raw_json, dict):
        return None

    server_raw = str(raw_json.get("server", "")).strip()
    if not server_raw:
        return None

    # 分离 host 与 port
    if server_raw.startswith("["):
        v6_match = re.match(r"^\\[(.*?)\\]:?(\\d+)?$", server_raw)
        if v6_match:
            host = v6_match.group(1)
            port = int(v6_match.group(2)) if v6_match.group(2) else 443
        else:
            host = server_raw
            port = 443
    elif ":" in server_raw:
        parts = server_raw.split(":")
        host = parts[0]
        port = int(parts[1]) if parts[1].isdigit() else 443
    else:
        host = server_raw
        port = int(raw_json.get("port", 443))

    auth = raw_json.get("auth") or raw_json.get("password") or ""
    tls_info = raw_json.get("tls") or {}
    bandwidth = raw_json.get("bandwidth") or {}
    transport = raw_json.get("transport") or {}
    quic_info = raw_json.get("quic") or {}

    sni = tls_info.get("sni") or host
    insecure = bool(tls_info.get("insecure", False))
    alpn = tls_info.get("alpn") or ["h3"]

    up_speed = bandwidth.get("up", "15 mbps")
    down_speed = bandwidth.get("down", "60 mbps")

    proxy = {
        "name": node_name,
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": str(auth),
        "sni": sni,
        "skip-cert-verify": insecure,
        "alpn": alpn,
        "up": str(up_speed),
        "down": str(down_speed),
    }

    # UDP 跃迁间隔
    udp_hop = transport.get("udp", {}).get("hopInterval")
    if udp_hop:
        digits = re.findall(r"\\d+", str(udp_hop))
        if digits:
            proxy["hop-interval"] = int(digits[0])

    # 混淆 (obfs) 支持
    obfs = raw_json.get("obfs")
    if obfs and isinstance(obfs, dict):
        if obfs.get("type"):
            proxy["obfs"] = obfs.get("type")
        if obfs.get("password"):
            proxy["obfs-password"] = obfs.get("password")

    return proxy

def generate_hy2_uri(proxy):
    """生成标准 hy2:// URI 链接"""
    pwd = quote(str(proxy.get("password", "")))
    sni = quote(str(proxy.get("sni", proxy["server"])))
    tag = quote(str(proxy["name"]))
    insecure = "1" if proxy.get("skip-cert-verify") else "0"
    return f"hy2://{pwd}@{proxy['server']}:{proxy['port']}/?sni={sni}&insecure={insecure}#{tag}"

def render_template(template_str, proxies):
    """
    填充模板并生成标准 YAML
    """
    if not proxies:
        return template_str.replace("{{proxies}}", "  # 暂无可用节点\\n").replace("{{proxy_names_indented}}", "      - DIRECT")

    # 序列化为 YAML 节点块 (保留 Unicode 中文字符)
    proxies_yaml = yaml.dump(proxies, allow_unicode=True, sort_keys=False)
    # 增加 2 空格缩进以匹配 proxies: 列表层级
    indented_proxies = "\\n".join(["  " + line for line in proxies_yaml.splitlines() if line.strip()])

    # 策略组列表缩进 (6 个空格)
    proxy_names_indented = "\\n".join([f'      - "{p["name"]}"' for p in proxies])
    proxy_names_list = "\\n".join([f'  - "{p["name"]}"' for p in proxies])

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    result = template_str.replace("{{proxies}}", indented_proxies)
    result = result.replace("{{proxy_names_indented}}", proxy_names_indented)
    result = result.replace("{{proxy_names}}", proxy_names_list)
    result = result.replace("{{node_count}}", str(len(proxies)))
    result = result.replace("{{generated_time}}", now_str)

    return result

def write_step_summary(items_count, success_nodes, fail_nodes):
    """向 GitHub Actions Job Summary 写入 Markdown 汇总报告"""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "## 🚀 节点自动化更新报告",
        f"**执行时间**: \`{now_str}\`",
        f"**节点统计**: 总任务 \`{items_count}\` 个 | 成功 \`{len(success_nodes)}\` 个 | 失败 \`{len(fail_nodes)}\` 个",
        "",
        "### ✅ 已成功生成的节点列表",
        "| 节点名称 | 服务器 | 端口 | 协议 | 线路状态 |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for p in success_nodes:
        status_tag = "🟡 备用镜像" if p.get("_is_mirror") else "🟢 主线路"
        lines.append(f"| **{p['name']}** | \`{p['server']}\` | \`{p['port']}\` | Hysteria2 | {status_tag} |")

    if fail_nodes:
        lines.extend([
            "",
            "### ❌ 获取失败的节点",
            "| 节点任务 | 主地址 | 状态 |",
            "| :--- | :--- | :--- |"
        ])
        for f in fail_nodes:
            lines.append(f"| {f['name']} | \`{f['primary']}\` | 连接超时或解析失败 |")

    lines.extend([
        "",
        "---",
        "💡 *订阅生成完毕，客户端已可通过 jsDelivr CDN 或 Raw 地址拉取最新配置。*"
    ])

    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\\n".join(lines) + "\\n")
    except Exception as e:
        print(f"[!] 写入 Summary 失败: {e}")

def main():
    print("=" * 65)
    print("🚀 开始运行 GitHub 节点提取与生成工作流")
    print("=" * 65)

    # 1. 提取 URL
    items = extract_node_items_from_file(URLS_FILE)
    if not items:
        print("[!] 未在 urls.txt 中找到任何可用 URL，程序退出")
        sys.exit(0)

    # 2. 依次下载并解析节点 (防重过滤)
    clash_proxies = []
    seen_endpoints = set()
    failed_items = []
    hy2_uris = []

    for item in items:
        print(f"\\n[*] 正在处理: {item['name']}")
        result = fetch_json_with_fallback(item["primary"], item.get("fallback"))
        if result and result.get("data"):
            proxy = convert_to_clash_proxy(result["data"], item["name"])
            if proxy:
                endpoint = f"{proxy['server']}:{proxy['port']}"
                if endpoint in seen_endpoints:
                    print(f"  [!] 提示: 该服务器节点已存在，保留当前实例")
                seen_endpoints.add(endpoint)

                proxy["_is_mirror"] = result.get("is_mirror", False)
                clash_proxies.append(proxy)
                hy2_uris.append(generate_hy2_uri(proxy))
                print(f"  [√] 成功生成: {proxy['name']} ➔ {proxy['server']}:{proxy['port']}")
            else:
                print(f"  [X] 格式转换失败")
                failed_items.append(item)
        else:
            print(f"  [X] 抓取失败 (主备镜像均不可达)")
            failed_items.append(item)

    print(f"\\n[=] 总计成功解析 {len(clash_proxies)} / {len(items)} 个可用节点")

    # 3. 读取模板并渲染 Clash Meta YAML
    if not os.path.exists(TEMPLATE_FILE):
        print(f"[错误] 模板文件未找到: {TEMPLATE_FILE}")
        sys.exit(1)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template_content = f.read()

    # 清理临时字段
    clean_proxies = []
    for p in clash_proxies:
        p_copy = dict(p)
        p_copy.pop("_is_mirror", None)
        clean_proxies.append(p_copy)

    rendered_yaml = render_template(template_content, clean_proxies)

    with open(CLASH_OUTPUT, "w", encoding="utf-8") as f:
        f.write(rendered_yaml)
    print(f"[√] 已写入 Clash Meta 订阅文件: {CLASH_OUTPUT}")

    # 4. 生成 Sing-box 格式 (singbox.json)
    try:
        singbox_outbounds = []
        for p in clean_proxies:
            up_num = int(re.findall(r"\\d+", str(p.get("up", "15")))[0]) if re.findall(r"\\d+", str(p.get("up", "15"))) else 15
            down_num = int(re.findall(r"\\d+", str(p.get("down", "60")))[0]) if re.findall(r"\\d+", str(p.get("down", "60"))) else 60

            singbox_outbounds.append({
                "type": "hysteria2",
                "tag": p["name"],
                "server": p["server"],
                "server_port": p["port"],
                "password": p.get("password", ""),
                "tls": {
                    "enabled": True,
                    "server_name": p.get("sni", p["server"]),
                    "insecure": p.get("skip-cert-verify", False),
                    "alpn": p.get("alpn", ["h3"])
                },
                "up_mbps": up_num,
                "down_mbps": down_num
            })

        with open(SINGBOX_OUTPUT, "w", encoding="utf-8") as f:
            json.dump({"outbounds": singbox_outbounds}, f, ensure_ascii=False, indent=2)
        print(f"[√] 已写入 Sing-Box 配置文件: {SINGBOX_OUTPUT}")
    except Exception as e:
        print(f"[!] 生成 Sing-Box 格式失败: {e}")

    # 5. 生成通用 Base64 订阅文本 (sub.txt)
    try:
        if hy2_uris:
            uris_text = "\\n".join(hy2_uris)
            b64_content = base64.b64encode(uris_text.encode("utf-8")).decode("utf-8")
            with open(BASE64_OUTPUT, "w", encoding="utf-8") as f:
                f.write(b64_content)
            print(f"[√] 已写入通用 Base64 订阅: {BASE64_OUTPUT}")
    except Exception as e:
        print(f"[!] 生成 Base64 订阅失败: {e}")

    # 6. 输出 GitHub Actions 统计摘要
    write_step_summary(len(items), clash_proxies, failed_items)

    print("=" * 65)
    print("✨ 所有工作流文件处理完成，准备提交！")
    print("=" * 65)

if __name__ == "__main__":
    main()
`;
}

export function generateGitignore(): string {
  return `# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.venv/
venv/
ENV/

# Logs & temp
*.log
*.tmp
.DS_Store
Thumbs.db
`;
}

export function generateRequirementsTxt(): string {
  return `requests>=2.31.0
pyyaml>=6.0.1
`;
}

export function generateLicense(username: string): string {
  const year = new Date().getFullYear();
  return `MIT License

Copyright (c) ${year} ${username || 'Node Subscription Maintainer'}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
`;
}

export function generateReadme(username: string, repo: string, targetFile: string): string {
  const user = username || '<YOUR_GITHUB_USERNAME>';
  const repository = repo || '<YOUR_REPO_NAME>';
  const file = targetFile || 'clash.yaml';

  return `# 🚀 GitHub 自动提取节点并生成 Clash 订阅

本项目通过 **GitHub Actions** 自动化定时任务：
1. 从 \`urls.txt\` (或您现有的批处理脚本) 中自动提取节点 JSON 链接；
2. 批量并发下载各节点最新配置，遇到主线路异常时自动切换备用镜像；
3. 将 Hysteria2 节点自动转换为标准 Clash Meta (Mihomo) 配置；
4. 按照 \`template.yaml\` 模板渲染生成带有分流策略组的完整订阅；
5. 定时自动提交并推送到 GitHub，免去手动维护的繁琐步骤。

---

## 📁 仓库完整目录结构

\`\`\`text
├── .github/
│   └── workflows/
│       └── update-nodes.yml    # GitHub Actions 定时更新工作流
├── scripts/
│   └── convert.py              # 核心转换脚本 (主备镜像容灾、协议转换、YAML渲染)
├── template.yaml               # Clash Meta 订阅分流规则与策略组模板
├── urls.txt                    # 待提取的 URL 文本 (可直接粘贴批处理 wget 命令)
├── requirements.txt            # Python 依赖清单 (requests, pyyaml)
├── .gitignore                  # Git 忽略配置
├── LICENSE                     # MIT 开源协议
├── ${file}                      # 自动生成的 Clash Meta 订阅文件 (客户端直接导入)
├── singbox.json                # 同步生成的 Sing-Box 配置文件
└── sub.txt                     # 同步生成的 Base64 通用订阅文本
\`\`\`

---

## ⚙️ 快速上手与部署步骤 (图文指南)

### 第一步：新建 GitHub 仓库
1. 登录 GitHub，点击右上角 **+** ➔ **New repository**。
2. 仓库建议设为 **Public** (公开仓库可使用免费 jsDelivr CDN 加速，客户端更新无需科学上网)。
3. 仓库名例如：\`my-nodes-sub\`，点击 **Create repository**。

### 第二步：上传仓库文件
将生成的工程文件上传或提交到仓库根目录：
- \`.github/workflows/update-nodes.yml\`
- \`scripts/convert.py\`
- \`template.yaml\`
- \`urls.txt\`
- \`requirements.txt\`
- \`.gitignore\`

### 第三步：开启 GitHub Actions 写入权限 (⚠️ 最关键的一步)
GitHub 默认限制 Actions 脚本向仓库写入提交，必须手动开启权限：
1. 进入您的 GitHub 仓库页面，点击上方的 **Settings** (设置)。
2. 点击左侧菜单中的 **Actions** ➔ **General**。
3. 滚动到页面底部的 **Workflow permissions**。
4. 勾选 **Read and write permissions** (允许读写权限)。
5. 点击绿色按钮 **Save** 保存。

### 第四步：手动测试运行
1. 点击仓库上方的 **Actions** 标签。
2. 在左侧列表点击 **自动提取节点并生成 Clash 订阅** 工作流。
3. 点击右侧的 **Run workflow** 下拉按钮 ➔ 点击绿色 **Run workflow**。
4. 稍等约 15~30 秒，工作流运行完成打上绿勾后，刷新仓库首页即可看到自动生成的 \`${file}\`、\`singbox.json\` 和 \`sub.txt\`！

---

## 🔗 获取订阅链接 (填入代理客户端)

### 方案 A：jsDelivr 全球高速 CDN (国内免翻墙首选 ⭐ 推荐)
无需翻墙即可在国内网络秒级拉取订阅更新：
\`\`\`text
https://fastly.jsdelivr.net/gh/${user}/${repository}@main/${file}
\`\`\`

### 方案 B：GhProxy 镜像加速通道
\`\`\`text
https://ghproxy.net/https://raw.githubusercontent.com/${user}/${repository}/main/${file}
\`\`\`

### 方案 C：GitHub 原生 Raw 链接
\`\`\`text
https://raw.githubusercontent.com/${user}/${repository}/main/${file}
\`\`\`

---

## 📱 客户端导入使用说明

### 1. Clash Verge Rev / Mihomo Party
- 打开客户端，点击 **订阅 (Subscriptions)** ➔ 粘贴上方复制的 **jsDelivr 订阅链接**。
- 点击 **保存并导入**。
- 在应用设置中确保内核选用 **Mihomo (Clash Meta)** 内核，即可全面支持 Hysteria 2 协议！

### 2. Shadowrocket (小火箭)
- 点击右上角 **+** 号，类型选择 **Subscribe**。
- URL 填入上方生成的链接，备注任意填写，点击完成即可自动更新节点。

### 3. Sing-box
- 导入仓库自动生成的 \`singbox.json\` 链接即可直接作为 outbounds 运行。

---

## ⏰ 定时自动更新频率
默认设定在每天 UTC 0:00、6:00、12:00、18:00 (即每 6 小时) 定时自动抓取并更新一次。
如需调整，请打开 \`.github/workflows/update-nodes.yml\` 修改 \`cron\` 参数：
- 每 2 小时运行一次：\`0 */2 * * *\`
- 每 4 小时运行一次：\`0 */4 * * *\`
- 每天北京时间早上 8 点运行一次：\`0 0 * * *\`

---

## ❓ 常见问题排查 (FAQ)

- **Q: 为什么 Actions 报错 \`Permission to ... denied to github-actions[bot]\`？**  
  A: 这是未开启写入权限导致的。请按上方【第三步】进入仓库 Settings ➔ Actions ➔ General ➔ Workflow permissions，勾选 **Read and write permissions**。

- **Q: 节点连不上或某些节点超时怎么办？**  
  A: 本工作流已自带**双线路主备镜像容灾**：当 GitLab Raw 链接超时，会自动切换至备用镜像。您也可以随时在 \`urls.txt\` 中增删或修改节点链接。
`;
}
