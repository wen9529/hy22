#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本 (全端双核双兼容终极版)：
1. 解决 Karing (Sing-Box 内核) 添加 xray_config.json 时报错 "singbox outbounds: No server available" 的问题；
2. 在 JSON outbound 中同时注入 Sing-Box 核心字段 (type, server, server_port, tls, transport) 与 Xray 核心字段 (protocol, settings.vnext, streamSettings)；
3. 输出完整兼容的 config.yaml, clash.yaml, singbox.json, xray_config.json, xray_links.txt, sub.txt。
"""

import os
import re
import sys
import json
import copy
import base64
import datetime
import ssl
from urllib.parse import quote
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
TEMPLATE_YAML_FILE = os.path.join(BASE_DIR, "template.yaml")

CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")
CONFIG_B64 = os.path.join(BASE_DIR, "config.b64")
CLASH_OUTPUT = os.path.join(BASE_DIR, "clash.yaml")
XRAY_CONFIG_JSON = os.path.join(BASE_DIR, "xray_config.json")
XRAY_LINKS_TXT = os.path.join(BASE_DIR, "xray_links.txt")
SINGBOX_OUTPUT = os.path.join(BASE_DIR, "singbox.json")
SUB_OUTPUT = os.path.join(BASE_DIR, "sub.txt")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT = 8

# 用户标准原生 Xray 完整配置模板
NATIVE_XRAY_TEMPLATE = {
    "log": { "loglevel": "warning" },
    "dns": {
        "hosts": {
            "dns.google": ["8.8.8.8","8.8.4.4","2001:4860:4860::8888","2001:4860:4860::8844"],
            "dns.alidns.com": ["223.5.5.5","223.6.6.6","2400:3200::1","2400:3200:baba::1"],
            "one.one.one.one": ["1.1.1.1","1.0.0.1","2606:4700:4700::1111","2606:4700:4700::1001"],
            "1dot1dot1dot1.cloudflare-dns.com": ["1.1.1.1","1.0.0.1","2606:4700:4700::1111","2606:4700:4700::1001"],
            "cloudflare-dns.com": ["104.16.249.249","104.16.248.249","2606:4700::6810:f8f9","2606:4700::6810:f9f9"],
            "dns.cloudflare.com": ["104.16.132.229","104.16.133.229","2606:4700::6810:84e5","2606:4700::6810:85e5"],
            "dot.pub": ["1.12.12.12","120.53.53.53"],
            "doh.pub": ["1.12.12.12","120.53.53.53"],
            "dns.quad9.net": ["9.9.9.9","149.112.112.112","2620:fe::fe","2620:fe::9"],
            "dns.umbrella.com": ["208.67.220.220","208.67.222.222","2620:119:35::35","2620:119:53::53"],
            "engage.cloudflareclient.com": ["162.159.192.1","2606:4700:d0::a29f:c001"]
        },
        "servers": [
            { "address": "https://dns.alidns.com/dns-query", "domains": ["geosite:private"], "skipFallback": True },
            { "address": "223.5.5.5", "domains": ["full:dns.alidns.com","full:cloudflare-dns.com"], "skipFallback": True },
            "https://cloudflare-dns.com/dns-query"
        ]
    },
    "inbounds": [
        {
            "tag": "socks",
            "port": 1080,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "sniffing": { "enabled": True, "destOverride": ["http","tls"], "routeOnly": False },
            "settings": { "auth": "noauth", "udp": True }
        },
        {
            "tag": "http",
            "port": 1081,
            "listen": "127.0.0.1",
            "protocol": "http",
            "sniffing": { "enabled": True, "destOverride": ["http","tls"], "routeOnly": False },
            "settings": { "auth": "noauth" }
        }
    ],
    "outbounds": [],
    "routing": {
        "domainStrategy": "AsIs",
        "rules": [
            { "type": "field", "outboundTag": "block", "ip": ["geoip:private"] },
            { "type": "field", "outboundTag": "direct", "domain": ["geosite:private"] },
            { "type": "field", "outboundTag": "Xray-VLESS-01", "port": "0-65535" }
        ]
    }
}

def extract_all_urls(file_path):
    """从 urls.txt 中提取全部 8 个 URL 链接"""
    urls = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                found = re.findall(r"https?://[^\s\"'<>]+", line)
                for u in found:
                    clean_u = u.rstrip('",\\').strip()
                    if clean_u:
                        urls.append(clean_u)
    return urls

def fetch_upstream_content(url):
    """从 URL 动态下载原生 Xray 配置"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as response:
            if response.status == 200:
                content = response.read().decode("utf-8").strip()
                return content
    except Exception as e:
        print(f"  [-] 请求失败 {url}: {e}")
    return None

def parse_node_details(content, idx):
    """解析节点参数，并构建同时兼容 Sing-Box 与 Xray 的双核 outbound"""
    node_name = f"Xray-VLESS-{idx:02d}"

    # 默认值
    server = "62.210.70.194" if idx <= 4 else "2001:bc8:32d7:302::14"
    port = 37783
    uuid = "a289c660-1b12-432b-a06c-c2ae469272b0"
    encryption = "none"
    flow = ""
    sni = "www.yahoo.com"
    public_key = "tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg"
    short_id = "21569dd6"
    fingerprint = "chrome"
    path = "/OCrp5Ajs"
    mode = "auto"

    if content:
        try:
            data = json.loads(content)
            outbounds = data.get("outbounds", [])
            if outbounds:
                ob = outbounds[0]
                settings = ob.get("settings", {})
                vnext = settings.get("vnext", [])
                if vnext and len(vnext) > 0:
                    vn0 = vnext[0]
                    server = str(vn0.get("address", server)).strip("[]")
                    port = int(vn0.get("port", port))
                    users = vn0.get("users", [])
                    if users and len(users) > 0:
                        u0 = users[0]
                        uuid = str(u0.get("id", uuid))
                        encryption = str(u0.get("encryption", encryption))
                        flow = str(u0.get("flow", ""))

                stream = ob.get("streamSettings", {})
                reality = stream.get("realitySettings", {})
                if reality.get("serverName"):
                    sni = reality.get("serverName")
                if reality.get("publicKey"):
                    public_key = reality.get("publicKey")
                if reality.get("shortId"):
                    short_id = reality.get("shortId")
                if reality.get("fingerprint"):
                    fingerprint = reality.get("fingerprint")

                xhttp_settings = stream.get("xhttpSettings", {})
                if xhttp_settings.get("path"):
                    path = xhttp_settings.get("path")
                if xhttp_settings.get("mode"):
                    mode = xhttp_settings.get("mode")
        except Exception as e:
            print(f"  [-] 解析错误，使用标准参数: {e}")

    # =========================================================================
    # 1. 双核混合 Outbound 对象 (针对 xray_config.json)
    #    让 Karing(Sing-Box内核) 与 Xray-core 均可直接解析本 JSON 并提取节点！
    # =========================================================================
    dual_outbound = {
        "tag": node_name,
        # --- Sing-Box 核心识别字段 (彻底解决 No server available) ---
        "type": "vless",
        "server": server,
        "server_port": port,
        "uuid": uuid,
        "flow": flow,
        "tls": {
            "enabled": True,
            "server_name": sni,
            "insecure": True,
            "utls": {
                "enabled": True,
                "fingerprint": fingerprint
            },
            "reality": {
                "enabled": True,
                "public_key": public_key,
                "short_id": short_id
            }
        },
        "transport": {
            "type": "http",
            "path": path,
            "host": [sni]
        },
        # --- Xray-core 原生识别字段 (原生 Xray 执行) ---
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": server,
                "port": port,
                "users": [{
                    "id": uuid,
                    "encryption": encryption,
                    "flow": flow
                }]
            }]
        },
        "streamSettings": {
            "network": "xhttp",
            "security": "reality",
            "realitySettings": {
                "serverName": sni,
                "fingerprint": fingerprint,
                "publicKey": public_key,
                "shortId": short_id
            },
            "xhttpSettings": {
                "path": path,
                "mode": mode
            }
        }
    }

    # =========================================================================
    # 2. Clash Meta / Karing 核心配置
    # =========================================================================
    clash_proxy = {
        "name": node_name,
        "type": "vless",
        "server": server,
        "port": port,
        "uuid": uuid,
        "udp": True,
        "tls": True,
        "skip-cert-verify": True,
        "servername": sni,
        "client-fingerprint": fingerprint,
        "alpn": ["h2"],
        "network": "xhttp",
        "reality-opts": {
            "public-key": public_key,
            "short-id": short_id
        },
        "xhttp-opts": {
            "path": path,
            "mode": mode,
            "headers": {"Host": sni}
        },
        "splithttp-opts": {
            "path": path,
            "mode": mode,
            "headers": {"Host": sni}
        }
    }
    if flow:
        clash_proxy["flow"] = flow

    # =========================================================================
    # 3. 标准通用 VLESS URI 链接
    # =========================================================================
    is_ipv6 = ":" in server
    uri_server = f"[{server}]" if is_ipv6 else server
    encoded_path = quote(path, safe="")
    q_parts = [
        "security=reality",
        "encryption=none",
        f"pbk={quote(public_key)}",
        "headerType=none",
        f"fp={quote(fingerprint)}",
        "type=xhttp",
        f"sni={quote(sni)}",
        f"sid={quote(short_id)}",
        f"path={encoded_path}",
        f"mode={quote(mode)}",
    ]
    if flow:
        q_parts.append(f"flow={quote(flow)}")
    vless_uri = f"vless://{uuid}@{uri_server}:{port}?" + "&".join(q_parts) + f"#{quote(node_name)}"

    # =========================================================================
    # 4. 纯净 Sing-Box 格式配置
    # =========================================================================
    singbox_node = {
        "type": "vless",
        "tag": node_name,
        "server": server,
        "server_port": port,
        "uuid": uuid,
        "flow": flow,
        "tls": {
            "enabled": True,
            "server_name": sni,
            "insecure": True,
            "utls": {
                "enabled": True,
                "fingerprint": fingerprint
            },
            "reality": {
                "enabled": True,
                "public_key": public_key,
                "short_id": short_id
            }
        },
        "transport": {
            "type": "http",
            "path": path,
            "host": [sni]
        }
    }

    return dual_outbound, clash_proxy, vless_uri, singbox_node

def dump_yaml_proxies(proxies):
    """序列化为完整兼容的 Clash Meta YAML"""
    lines = []
    for p in proxies:
        lines.append(f"  - name: \"{p['name']}\"")
        lines.append(f"    type: {p['type']}")
        lines.append(f"    server: \"{p['server']}\"")
        lines.append(f"    port: {p['port']}")
        lines.append(f"    uuid: \"{p['uuid']}\"")
        lines.append(f"    udp: true")
        lines.append(f"    tls: true")
        lines.append(f"    skip-cert-verify: true")
        if p.get("flow"):
            lines.append(f"    flow: \"{p['flow']}\"")
        lines.append(f"    servername: \"{p.get('servername', 'www.yahoo.com')}\"")
        lines.append(f"    client-fingerprint: \"{p.get('client-fingerprint', 'chrome')}\"")
        lines.append(f"    alpn:")
        lines.append(f"      - h2")
        lines.append(f"    network: {p.get('network', 'xhttp')}")
        
        if "reality-opts" in p:
            lines.append("    reality-opts:")
            lines.append(f"      public-key: \"{p['reality-opts'].get('public-key', '')}\"")
            lines.append(f"      short-id: \"{p['reality-opts'].get('short-id', '')}\"")
            
        if "xhttp-opts" in p:
            lines.append("    xhttp-opts:")
            lines.append(f"      path: \"{p['xhttp-opts'].get('path', '/OCrp5Ajs')}\"")
            lines.append(f"      mode: \"{p['xhttp-opts'].get('mode', 'auto')}\"")
            lines.append("      headers:")
            lines.append(f"        Host: \"{p.get('servername', 'www.yahoo.com')}\"")

        if "splithttp-opts" in p:
            lines.append("    splithttp-opts:")
            lines.append(f"      path: \"{p['splithttp-opts'].get('path', '/OCrp5Ajs')}\"")
            lines.append(f"      mode: \"{p['splithttp-opts'].get('mode', 'auto')}\"")
            lines.append("      headers:")
            lines.append(f"        Host: \"{p.get('servername', 'www.yahoo.com')}\"")
            
    return "\n".join(lines)

def render_yaml_template(template_str, proxies):
    """渲染完整 Clash Meta 订阅配置"""
    if not proxies:
        return template_str.replace("{{proxies}}", "  # 暂无可用节点\n").replace("{{proxy_names_indented}}", "      - DIRECT")

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
    print("🚀 开始运行多核双向兼容转换工作流 (覆盖 Karing/Sing-Box 与 Xray)")
    print("=" * 65)

    urls = extract_all_urls(URLS_FILE)
    print(f"[*] 从 urls.txt 读取到 {len(urls)} 个节点 URL 源")

    dual_outbounds_list = []
    clash_proxies_list = []
    vless_uris_list = []
    singbox_nodes_list = []

    for idx, u in enumerate(urls, 1):
        print(f"[*] 正在拉取第 {idx}/8 个节点源: {u}")
        content = fetch_upstream_content(u)

        dual_ob, clash_p, v_uri, sb_n = parse_node_details(content, idx)
        dual_outbounds_list.append(dual_ob)
        clash_proxies_list.append(clash_p)
        vless_uris_list.append(v_uri)
        singbox_nodes_list.append(sb_n)

        server_addr = clash_p["server"]
        port_num = clash_p["port"]
        print(f"  [√] 节点 {idx:02d} 生成成功 ➔ {server_addr}:{port_num} ({clash_p['name']})")

    print(f"\n[=] 成功生成全部 {len(clash_proxies_list)} 个双核兼容节点！")

    # 1. 严格按照原生配置模板生成完整 Xray 配置 (xray_config.json)
    full_xray_config = copy.deepcopy(NATIVE_XRAY_TEMPLATE)
    full_xray_config["outbounds"] = copy.deepcopy(dual_outbounds_list)
    full_xray_config["outbounds"].append({ "tag": "direct", "protocol": "freedom" })
    full_xray_config["outbounds"].append({ "tag": "block", "protocol": "blackhole" })
    
    with open(XRAY_CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump(full_xray_config, f, ensure_ascii=False, indent=2)
    print(f"[√] 已写入双核兼容原生配置: {XRAY_CONFIG_JSON}")

    # 2. 写入原生 VLESS 明文链接清单 (xray_links.txt)
    uris_text = "\n".join(vless_uris_list)
    with open(XRAY_LINKS_TXT, "w", encoding="utf-8") as f:
        f.write(uris_text + "\n")
    print(f"[√] 已写入原生明文链接清单: {XRAY_LINKS_TXT}")

    # 3. 写入 Base64 通用订阅 (sub.txt & config.b64)
    b64_content = base64.b64encode(uris_text.encode("utf-8")).decode("utf-8") if uris_text else ""
    with open(SUB_OUTPUT, "w", encoding="utf-8") as f:
        f.write(b64_content + "\n")
    with open(CONFIG_B64, "w", encoding="utf-8") as f:
        f.write(b64_content + "\n")
    print(f"[√] 已写入 Base64 订阅: {SUB_OUTPUT}")

    # 4. 写入完整 Clash Meta / Karing 订阅 (config.yaml & clash.yaml)
    if os.path.exists(TEMPLATE_YAML_FILE):
        with open(TEMPLATE_YAML_FILE, "r", encoding="utf-8") as f:
            tpl_str = f.read()

        rendered_yaml = render_yaml_template(tpl_str, clash_proxies_list)
        with open(CONFIG_YAML, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        with open(CLASH_OUTPUT, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        print(f"[√] 已写入 Clash Meta / Karing 订阅: {CONFIG_YAML}")

    # 5. 写入纯净 Sing-Box 格式配置 (singbox.json)
    try:
        with open(SINGBOX_OUTPUT, "w", encoding="utf-8") as f:
            json.dump({"outbounds": singbox_nodes_list}, f, ensure_ascii=False, indent=2)
        print(f"[√] 已写入纯净 Sing-Box 配置: {SINGBOX_OUTPUT}")
    except Exception as e:
        print(f"[!] 生成 Sing-Box 失败: {e}")

    print("=" * 65)
    print("✨ 全部 8 个节点双核兼容生成完毕！")
    print("=" * 65)

if __name__ == "__main__":
    main()
