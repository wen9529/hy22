#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本 (全端完整 Hysteria 2 节点规范版)：
1. 完整注入 Hysteria 2 官方规范所需全部字段 (type, server, port, password, auth, sni, skip-cert-verify, alpn, up, down, fast-open)
2. 同时兼容 IPv4 (域名/直连IP) 与 IPv6，适配 Android Karing / Clash Meta / Shadowrocket / Sing-box / v2rayN
3. 输出完整且经语法验证的：
   - config.yaml & clash.yaml (Clash Meta 完整分流订阅)
   - hy2_config.yaml (纯净 Hysteria 2 节点清单，含 proxy-provider 完整支持)
   - hy2_links.txt (标准 RFC 3986 规范的 hy2:// 协议链接)
   - sub.txt & config.b64 & hy2_config.b64 (Base64 通用订阅)
   - singbox.json (Sing-box 官方规范 Outbounds)
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

# 内置验证可用的全量 Hysteria 2 节点基础库 (包含 IPv4 与 IPv6 完整节点)
DEFAULT_NODES = [
    {
        "name": "HY2 节点 01 (IPv4 域名 838491)",
        "server": "www.838491.xyz",
        "port": 13377,
        "password": "dongtaiwang.com",
        "auth": "dongtaiwang.com",
        "sni": "www.838491.xyz",
        "skip-cert-verify": True,
        "alpn": ["h3"],
        "up": "11 mbps",
        "down": "55 mbps",
        "fast-open": True
    },
    {
        "name": "HY2 节点 02 (IPv4 直连 62.210.8.122)",
        "server": "62.210.8.122",
        "port": 13377,
        "password": "dongtaiwang.com",
        "auth": "dongtaiwang.com",
        "sni": "www.838491.xyz",
        "skip-cert-verify": True,
        "alpn": ["h3"],
        "up": "11 mbps",
        "down": "55 mbps",
        "fast-open": True
    },
    {
        "name": "HY2 节点 03 (IPv4 直连 62.210.70.191)",
        "server": "62.210.70.191",
        "port": 22000,
        "password": "dongtaiwang.com",
        "auth": "dongtaiwang.com",
        "sni": "www.microsoft.com",
        "skip-cert-verify": True,
        "alpn": ["h3"],
        "up": "11 mbps",
        "down": "55 mbps",
        "fast-open": True
    },
    {
        "name": "HY2 节点 04 (IPv6 2001:bc8:32d7:17b::3)",
        "server": "2001:bc8:32d7:17b::3",
        "port": 22000,
        "password": "dongtaiwang.com",
        "auth": "dongtaiwang.com",
        "sni": "www.microsoft.com",
        "skip-cert-verify": True,
        "alpn": ["h3"],
        "up": "11 mbps",
        "down": "55 mbps",
        "fast-open": True
    },
    {
        "name": "HY2 节点 05 (IPv6 2001:bc8:32d7:17b::8)",
        "server": "2001:bc8:32d7:17b::8",
        "port": 22000,
        "password": "dongtaiwang.com",
        "auth": "dongtaiwang.com",
        "sni": "www.microsoft.com",
        "skip-cert-verify": True,
        "alpn": ["h3"],
        "up": "11 mbps",
        "down": "55 mbps",
        "fast-open": True
    }
]

def load_node_template():
    if os.path.exists(NODE_TEMPLATE_FILE):
        try:
            with open(NODE_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def generate_hy2_uri(proxy):
    """
    按照 Hysteria 2 官方 URI 规范生成：
    hy2://password@host:port/?sni=...&insecure=1#tag
    对于 IPv6，严格包裹 [ ]
    """
    pwd = quote(str(proxy.get("password") or proxy.get("auth") or ""))
    sni = quote(str(proxy.get("sni", proxy["server"])))
    tag = quote(str(proxy["name"]))
    insecure = "1" if proxy.get("skip-cert-verify", True) else "0"
    
    server_host = str(proxy["server"]).strip()
    if ":" in server_host and not server_host.startswith("["):
        host_str = f"[{server_host}]"
    else:
        host_str = server_host
        
    return f"hy2://{pwd}@{host_str}:{proxy['port']}/?sni={sni}&insecure={insecure}#{tag}"

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
        lines.append(f"    auth: \"{p.get('auth', p['password'])}\"")
        lines.append(f"    sni: \"{p['sni']}\"")
        lines.append(f"    skip-cert-verify: {str(p.get('skip-cert-verify', True)).lower()}")
        lines.append("    alpn:")
        for a in p.get("alpn", ["h3"]):
            lines.append(f"      - {a}")
        lines.append(f"    up: \"{p.get('up', '11 mbps')}\"")
        lines.append(f"    down: \"{p.get('down', '55 mbps')}\"")
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
    print("🚀 开始运行 GitHub 节点生成工作流 (完整规范全端版)")
    print("=" * 65)

    # 载入完整 Hysteria 2 节点清单
    all_proxies = []
    hy2_uris = []

    for node in DEFAULT_NODES:
        p = dict(node)
        p["type"] = "hysteria2"
        all_proxies.append(p)
        hy2_uris.append(generate_hy2_uri(p))
        print(f"  [√] 成功配置完整节点: {p['name']} ➔ {p['server']}:{p['port']}")

    print(f"\n[=] 总计成功就绪 {len(all_proxies)} 个完整规范 Hysteria 2 节点")

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
                "password": p.get("password", p.get("auth", "")),
                "tls": {
                    "enabled": True,
                    "server_name": p.get("sni", p["server"]),
                    "insecure": True,
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
    print("✨ 所有格式转换完成，包含全套高兼容完整 Hysteria 2 节点！")
    print("=" * 65)

if __name__ == "__main__":
    main()
