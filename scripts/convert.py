#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本 (IPv4 模板适配版)：
1. 按照用户指定的 IPv4 模板 (node_template.json) 修改并注入服务器地址、端口与 TLS 证书配置
2. 采用 IPv4 域名 (www.838491.xyz:13377) 与 IPv4 直连 (62.210.8.122:13377)，彻底解决国内网络无 IPv6 无法连通的问题
3. 按照 template.yaml 渲染并输出：
   - config.yaml & clash.yaml (Clash Meta 完整分流配置，含自动测速与负载均衡)
   - hy2_config.yaml (纯净 Hysteria 2 节点清单)
   - hy2_links.txt (标准 hy2:// URI 清单，insecure=0)
   - config.b64 & hy2_config.b64 & sub.txt (Base64 通用订阅)
   - singbox.json (Sing-box 官方格式)
"""

import os
import re
import sys
import json
import base64
import datetime
import ssl
from urllib.parse import quote
import urllib.request

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

try:
    import yaml
    HAS_YAML = True
except Exception:
    HAS_YAML = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
URLS_HY2_FILE = os.path.join(BASE_DIR, "urls_hy2.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.yaml")
NODE_TEMPLATE_FILE = os.path.join(BASE_DIR, "node_template.json")

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

# 默认用户指定的 IPv4 模板规范
DEFAULT_TEMPLATE_DATA = {
    "server": "www.838491.xyz:13377",
    "ipv4": "62.210.8.122",
    "auth": "dongtaiwang.com",
    "bandwidth": {
        "up": "11 mbps",
        "down": "55 mbps"
    },
    "tls": {
        "sni": "www.838491.xyz",
        "insecure": False
    },
    "transport": {
        "udp": {
            "hopInterval": "30s"
        }
    }
}

def load_node_template():
    if os.path.exists(NODE_TEMPLATE_FILE):
        try:
            with open(NODE_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] 读取 node_template.json 失败: {e}，使用内置默认模板")
    return DEFAULT_TEMPLATE_DATA

def extract_node_items_from_files(file_paths):
    all_content = ""
    for path in file_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                all_content += "\n" + f.read()

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
            "name": f"Hysteria2-{i:02d}",
            "primary": url,
            "fallback": None
        })

    # 如果没有读取到任何 URL，默认提供 4 个标准节点编号
    if not items:
        for idx in range(1, 5):
            items.append({
                "name": f"Hysteria2-{idx:02d}",
                "primary": None,
                "fallback": None
            })

    print(f"[*] 成功识别 {len(items)} 个节点任务")
    return items

def build_clash_proxies_from_template(node_name, template_data):
    """
    根据 IPv4 模板生成标准 Clash Meta 节点：
    1. 域名线路 (www.838491.xyz:13377)
    2. IPv4 直连线路 (62.210.8.122:13377)
    """
    server_str = template_data.get("server", "www.838491.xyz:13377")
    if ":" in server_str:
        host, port_str = server_str.split(":", 1)
        port = int(port_str) if port_str.isdigit() else 13377
    else:
        host = server_str
        port = 13377

    ipv4_direct = template_data.get("ipv4", "62.210.8.122")
    auth = template_data.get("auth", "dongtaiwang.com")
    tls_info = template_data.get("tls", {})
    sni = tls_info.get("sni", host)
    insecure = bool(tls_info.get("insecure", False)) # 严格按照模板为 false

    bandwidth = template_data.get("bandwidth", {})
    up = bandwidth.get("up", "11 mbps")
    down = bandwidth.get("down", "55 mbps")

    proxies = []

    # 1. 域名解析线路
    p_domain = {
        "name": f"{node_name}",
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": str(auth),
        "sni": sni,
        "skip-cert-verify": insecure,
        "alpn": ["h3"],
        "up": str(up),
        "down": str(down),
        "fast-open": True
    }
    proxies.append(p_domain)

    # 2. IPv4 直连纯 IP 线路 (防 DNS 污染与解析失败)
    if ipv4_direct and ipv4_direct != host:
        p_ipv4 = {
            "name": f"{node_name} [IPv4直连]",
            "type": "hysteria2",
            "server": ipv4_direct,
            "port": port,
            "password": str(auth),
            "sni": sni,
            "skip-cert-verify": insecure,
            "alpn": ["h3"],
            "up": str(up),
            "down": str(down),
            "fast-open": True
        }
        proxies.append(p_ipv4)

    return proxies

def generate_hy2_uri(proxy):
    pwd = quote(str(proxy.get("password", "")))
    sni = quote(str(proxy.get("sni", proxy["server"])))
    tag = quote(str(proxy["name"]))
    insecure = "1" if proxy.get("skip-cert-verify") else "0"
    return f"hy2://{pwd}@{proxy['server']}:{proxy['port']}/?sni={sni}&insecure={insecure}#{tag}"

def dump_yaml_proxies(proxies):
    if HAS_YAML:
        return yaml.dump(proxies, allow_unicode=True, sort_keys=False)
    
    lines = []
    for p in proxies:
        lines.append(f"  - name: \"{p['name']}\"")
        lines.append(f"    type: {p['type']}")
        lines.append(f"    server: \"{p['server']}\"")
        lines.append(f"    port: {p['port']}")
        lines.append(f"    password: \"{p['password']}\"")
        lines.append(f"    sni: \"{p['sni']}\"")
        lines.append(f"    skip-cert-verify: {str(p['skip-cert-verify']).lower()}")
        lines.append("    alpn:")
        for a in p.get("alpn", ["h3"]):
            lines.append(f"      - {a}")
        lines.append(f"    up: \"{p['up']}\"")
        lines.append(f"    down: \"{p['down']}\"")
        lines.append(f"    fast-open: {str(p.get('fast-open', True)).lower()}")
    return "\n".join(lines)

def render_template(template_str, proxies):
    if not proxies:
        return template_str.replace("{{proxies}}", "  # 暂无可用节点\n").replace("{{proxy_names_indented}}", "      - DIRECT")

    if HAS_YAML:
        proxies_yaml = yaml.dump(proxies, allow_unicode=True, sort_keys=False)
        indented_proxies = "\n".join(["  " + line for line in proxies_yaml.splitlines() if line.strip()])
    else:
        indented_proxies = dump_yaml_proxies(proxies)

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
    print("🚀 开始运行 GitHub 节点生成工作流 (IPv4 模板适配版)")
    print("=" * 65)

    template_data = load_node_template()
    server_info = template_data.get("server", "www.838491.xyz:13377")
    ipv4_info = template_data.get("ipv4", "62.210.8.122")
    print(f"[*] 目标服务器: {server_info} (IPv4直连: {ipv4_info})")
    print(f"[*] SNI: {template_data.get('tls', {}).get('sni')}, Insecure: {template_data.get('tls', {}).get('insecure')}")

    input_files = [URLS_HY2_FILE, URLS_FILE]
    items = extract_node_items_from_files(input_files)

    all_proxies = []
    hy2_uris = []

    for item in items:
        # 按照用户提供的 IPv4 模板修改与组装服务器地址端口
        proxies = build_clash_proxies_from_template(item["name"], template_data)
        for p in proxies:
            all_proxies.append(p)
            hy2_uris.append(generate_hy2_uri(p))
            print(f"  [√] 成功生成: {p['name']} ➔ {p['server']}:{p['port']}")

    print(f"\n[=] 总计成功生成 {len(all_proxies)} 个 IPv4 节点")

    # 1. 纯 Hysteria 2 节点清单 (hy2_config.yaml)
    clean_proxies = [dict(p) for p in all_proxies]
    if HAS_YAML:
        hy2_yaml_content = yaml.dump({"proxies": clean_proxies}, allow_unicode=True, sort_keys=False)
    else:
        hy2_yaml_content = "proxies:\n" + dump_yaml_proxies(clean_proxies)
    with open(HY2_CONFIG_YAML, "w", encoding="utf-8") as f:
        f.write(hy2_yaml_content)
    print(f"[√] 已写入纯 Hysteria 2 节点配置: {HY2_CONFIG_YAML}")

    # 2. 原生 hy2:// 节点链接清单 (hy2_links.txt)
    uris_text = "\n".join(hy2_uris)
    with open(HY2_LINKS_TXT, "w", encoding="utf-8") as f:
        f.write(uris_text)
    print(f"[√] 已写入 RFC 3986 规范的 URI 清单: {HY2_LINKS_TXT}")

    # 3. Base64 订阅 (hy2_config.b64 & sub.txt)
    b64_content = base64.b64encode(uris_text.encode("utf-8")).decode("utf-8") if uris_text else ""
    with open(HY2_CONFIG_B64, "w", encoding="utf-8") as f:
        f.write(b64_content)
    with open(SUB_OUTPUT, "w", encoding="utf-8") as f:
        f.write(b64_content)
    print(f"[√] 已写入 Base64 订阅: {SUB_OUTPUT}")

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

        config_b64 = base64.b64encode(rendered_yaml.encode("utf-8")).decode("utf-8")
        with open(CONFIG_B64, "w", encoding="utf-8") as f:
            f.write(config_b64)
        print(f"[√] 已写入 config.b64")

    # 5. Sing-Box 格式 (singbox.json)
    try:
        singbox_outbounds = []
        for p in clean_proxies:
            up_num = int(re.findall(r"\d+", str(p.get("up", "11")))[0]) if re.findall(r"\d+", str(p.get("up", "11"))) else 11
            down_num = int(re.findall(r"\d+", str(p.get("down", "55")))[0]) if re.findall(r"\d+", str(p.get("down", "55"))) else 55
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
                    "alpn": ["h3"]
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
    print("✨ 所有格式转换完成，包含全套 IPv4 优化节点！")
    print("=" * 65)

if __name__ == "__main__":
    main()
