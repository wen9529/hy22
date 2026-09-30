#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本：
1. 自动读取 urls.txt 与 urls_hy2.txt 中的节点配置链接
2. 批量请求 URL 下载 Hysteria 2 节点 JSON 配置文件，支持双镜像自动容灾
3. 按照 template.yaml 模板渲染并生成：
   - config.yaml (完整 Clash Meta 订阅)
   - config.b64 (Base64 订阅)
   - hy2_config.yaml (纯 Hysteria 2 代理配置)
   - hy2_config.b64 (纯 Hysteria 2 Base64 订阅)
   - hy2_links.txt (原生 hy2:// 节点链接清单)
   - clash.yaml (向后兼容)
   - singbox.json (Sing-box 格式)
"""

import os
import re
import sys
import json
import base64
import datetime
from urllib.parse import quote

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    os.system("pip install requests pyyaml")
    import requests

try:
    import yaml
except ImportError:
    os.system("pip install pyyaml")
    import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
URLS_HY2_FILE = os.path.join(BASE_DIR, "urls_hy2.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.yaml")

# 输出文件清单 (与标准仓库布局完全一致)
CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")
CONFIG_B64 = os.path.join(BASE_DIR, "config.b64")
HY2_CONFIG_YAML = os.path.join(BASE_DIR, "hy2_config.yaml")
HY2_CONFIG_B64 = os.path.join(BASE_DIR, "hy2_config.b64")
HY2_LINKS_TXT = os.path.join(BASE_DIR, "hy2_links.txt")
CLASH_OUTPUT = os.path.join(BASE_DIR, "clash.yaml")
SINGBOX_OUTPUT = os.path.join(BASE_DIR, "singbox.json")
SUB_OUTPUT = os.path.join(BASE_DIR, "sub.txt")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT = 12

def extract_node_items_from_files(file_paths):
    """从多个文本文件中提取 URL 并自动匹配主用与备用镜像"""
    all_content = ""
    for path in file_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                all_content += "\n" + f.read()

    if not all_content.strip():
        print("[错误] 未找到任何有效的 URL 输入文件")
        return []

    urls = re.findall(r"https?://[^\s\"'<>]+", all_content)
    cleaned_urls = [u.rstrip('",\\').strip() for u in urls if u.strip()]

    node_groups = {}
    unkeyed_urls = []

    for url in cleaned_urls:
        match = re.search(r"/hysteria2/(\d+)/", url, re.I) or re.search(r"/(\d+)/config\.json", url, re.I)
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
    for key, val in sorted(node_groups.items(), key=lambda x: x[1]["index"]):
        items.append({
            "name": f"Hysteria2-{val['index']:02d}",
            "primary": val["primary"],
            "fallback": val["fallback"]
        })

    for i, url in enumerate(unkeyed_urls, start=len(items) + 1):
        items.append({
            "name": f"Node-{i:02d}",
            "primary": url,
            "fallback": None
        })

    print(f"[*] 成功解析识别 {len(items)} 个节点任务 (含备用镜像通道)")
    return items

def fetch_json_with_fallback(primary_url, fallback_url=None):
    """请求 JSON 节点配置，主 URL 失败或超时自动尝试备用镜像"""
    urls_to_try = [u for u in [primary_url, fallback_url] if u]
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Connection": "close"
    }

    for idx, target_url in enumerate(urls_to_try):
        is_mirror = (idx > 0)
        mirror_tag = " [备用镜像]" if is_mirror else " [主线路]"

        for attempt in range(1, 3):
            try:
                resp = requests.get(target_url, headers=headers, timeout=TIMEOUT, verify=False)
                if resp.status_code == 200:
                    text_content = resp.text.strip()
                    try:
                        data = json.loads(text_content)
                        print(f"  [+] 下载成功{mirror_tag}: {target_url}")
                        return {"data": data, "active_url": target_url, "is_mirror": is_mirror}
                    except json.JSONDecodeError:
                        print(f"  [-] 返回内容非合法 JSON: {target_url}")
                else:
                    print(f"  [-] HTTP {resp.status_code}{mirror_tag}: {target_url}")
            except Exception as e:
                err_msg = "请求超时" if "timeout" in str(e).lower() else str(e)
                print(f"  [-] 连接失败 (第 {attempt} 次){mirror_tag}: {err_msg}")

    return None

def convert_to_clash_proxy(raw_json, node_name):
    """将 Hysteria 2 客户端 config.json 转换为 Clash Meta (Mihomo) 节点字典"""
    if not raw_json or not isinstance(raw_json, dict):
        return None

    server_raw = str(raw_json.get("server", "")).strip()
    if not server_raw:
        return None

    if server_raw.startswith("["):
        v6_match = re.match(r"^\[(.*?)\]:?(\d+)?$", server_raw)
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

    udp_hop = transport.get("udp", {}).get("hopInterval")
    if udp_hop:
        digits = re.findall(r"\d+", str(udp_hop))
        if digits:
            proxy["hop-interval"] = int(digits[0])

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
    """填充模板并生成标准 YAML"""
    if not proxies:
        return template_str.replace("{{proxies}}", "  # 暂无可用节点\n").replace("{{proxy_names_indented}}", "      - DIRECT")

    proxies_yaml = yaml.dump(proxies, allow_unicode=True, sort_keys=False)
    indented_proxies = "\n".join(["  " + line for line in proxies_yaml.splitlines() if line.strip()])
    proxy_names_indented = "\n".join([f'      - "{p["name"]}"' for p in proxies])
    proxy_names_list = "\n".join([f'  - "{p["name"]}"' for p in proxies])
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    result = template_str.replace("{{proxies}}", indented_proxies)
    result = result.replace("{{proxy_names_indented}}", proxy_names_indented)
    result = result.replace("{{proxy_names}}", proxy_names_list)
    result = result.replace("{{node_count}}", str(len(proxies)))
    result = result.replace("{{generated_time}}", now_str)
    return result

def main():
    print("=" * 65)
    print("🚀 开始运行 GitHub 节点提取与生成工作流")
    print("=" * 65)

    input_files = [URLS_HY2_FILE, URLS_FILE]
    items = extract_node_items_from_files(input_files)
    if not items:
        print("[!] 未找到任何可用 URL，程序退出")
        sys.exit(0)

    clash_proxies = []
    seen_endpoints = set()
    failed_items = []
    hy2_uris = []

    for item in items:
        print(f"\n[*] 正在处理: {item['name']}")
        result = fetch_json_with_fallback(item["primary"], item.get("fallback"))
        if result and result.get("data"):
            proxy = convert_to_clash_proxy(result["data"], item["name"])
            if proxy:
                endpoint = f"{proxy['server']}:{proxy['port']}"
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

    print(f"\n[=] 总计成功解析 {len(clash_proxies)} / {len(items)} 个可用节点")

    # 1. 纯 Hysteria 2 节点清单 (hy2_config.yaml)
    clean_proxies = []
    for p in clash_proxies:
        p_copy = dict(p)
        p_copy.pop("_is_mirror", None)
        clean_proxies.append(p_copy)

    hy2_yaml_content = yaml.dump({"proxies": clean_proxies}, allow_unicode=True, sort_keys=False)
    with open(HY2_CONFIG_YAML, "w", encoding="utf-8") as f:
        f.write(hy2_yaml_content)
    print(f"[√] 已写入纯 Hysteria 2 节点配置: {HY2_CONFIG_YAML}")

    # 2. 原生 hy2:// 节点链接清单 (hy2_links.txt)
    uris_text = "\n".join(hy2_uris)
    with open(HY2_LINKS_TXT, "w", encoding="utf-8") as f:
        f.write(uris_text)
    print(f"[√] 已写入原生链接清单: {HY2_LINKS_TXT}")

    # 3. Base64 编码 (hy2_config.b64 & sub.txt)
    b64_content = base64.b64encode(uris_text.encode("utf-8")).decode("utf-8") if uris_text else ""
    with open(HY2_CONFIG_B64, "w", encoding="utf-8") as f:
        f.write(b64_content)
    with open(SUB_OUTPUT, "w", encoding="utf-8") as f:
        f.write(b64_content)
    print(f"[√] 已写入 Base64 订阅: {HY2_CONFIG_B64}")

    # 4. 完整 Clash Meta 配置 (config.yaml & clash.yaml)
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template_content = f.read()

        rendered_yaml = render_template(template_content, clean_proxies)
        with open(CONFIG_YAML, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        with open(CLASH_OUTPUT, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        print(f"[√] 已写入完整 Clash 订阅: {CONFIG_YAML}")

        # 5. config.b64
        config_b64 = base64.b64encode(rendered_yaml.encode("utf-8")).decode("utf-8")
        with open(CONFIG_B64, "w", encoding="utf-8") as f:
            f.write(config_b64)
        print(f"[√] 已写入 config.b64")

    # 6. Sing-Box 格式 (singbox.json)
    try:
        singbox_outbounds = []
        for p in clean_proxies:
            up_num = int(re.findall(r"\d+", str(p.get("up", "15")))[0]) if re.findall(r"\d+", str(p.get("up", "15"))) else 15
            down_num = int(re.findall(r"\d+", str(p.get("down", "60")))[0]) if re.findall(r"\d+", str(p.get("down", "60"))) else 60
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
        print(f"[√] 已写入 Sing-Box 格式: {SINGBOX_OUTPUT}")
    except Exception as e:
        print(f"[!] 生成 Sing-Box 失败: {e}")

    print("=" * 65)
    print("✨ 所有格式转换完成，包含 config.yaml, hy2_config.yaml, hy2_links.txt！")
    print("=" * 65)

if __name__ == "__main__":
    main()
