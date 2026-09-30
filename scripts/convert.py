#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本 (Xray VLESS Reality 增强版)：
1. 自动提取 urls.txt 中的全部 Xray 配置，完整保留后量子加密 (mlkem768) 与 xhttp 传输协议；
2. 包含 4 组上游节点 + 备用自定义节点，确保节点列表完整；
3. 输出 Clash Meta / Karing、Xray 官方 JSON、Base64 通用订阅与 Sing-Box 格式。
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.yaml")

CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")
CONFIG_B64 = os.path.join(BASE_DIR, "config.b64")
CLASH_OUTPUT = os.path.join(BASE_DIR, "clash.yaml")
XRAY_CONFIG_JSON = os.path.join(BASE_DIR, "xray_config.json")
XRAY_LINKS_TXT = os.path.join(BASE_DIR, "xray_links.txt")
SINGBOX_OUTPUT = os.path.join(BASE_DIR, "singbox.json")
SUB_OUTPUT = os.path.join(BASE_DIR, "sub.txt")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TIMEOUT = 8

def extract_all_urls(file_path):
    """从输入文档中按顺序提取全部 URL 链接"""
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
                    if clean_u and clean_u not in urls:
                        urls.append(clean_u)
    return urls

def fetch_upstream_content(url):
    """从真实 URL 动态下载最新的配置"""
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

def parse_xray_node(content, default_name):
    """从 Xray config.json 中精准解析 VLESS Reality 节点 (含后量子加密密钥)"""
    if not content:
        return None, None, None
    
    try:
        data = json.loads(content)
    except Exception as e:
        print(f"  [-] JSON 解析异常: {e}")
        return None, None, None
    
    outbounds = data.get("outbounds", [])
    if not outbounds:
        return None, None, None
    
    proxy_ob = None
    for ob in outbounds:
        proto = str(ob.get("protocol", "")).lower()
        if proto in ["vless", "vmess", "trojan", "shadowsocks"]:
            proxy_ob = ob
            break
    
    if not proxy_ob:
        proxy_ob = outbounds[0]
    
    proto = str(proxy_ob.get("protocol", "vless")).lower()
    settings = proxy_ob.get("settings", {})
    vnext = settings.get("vnext", [])
    
    server = "62.210.70.194"
    port = 37783
    uuid = "a289c660-1b12-432b-a06c-c2ae469272b0"
    encryption = "none"
    flow = ""
    
    if vnext and isinstance(vnext, list) and len(vnext) > 0:
        vn0 = vnext[0]
        server = str(vn0.get("address", server)).strip("[]")
        port = int(vn0.get("port", port))
        users = vn0.get("users", [])
        if users and len(users) > 0:
            uuid = str(users[0].get("id", uuid))
            encryption = str(users[0].get("encryption", "none"))
            flow = str(users[0].get("flow", ""))
    
    stream = proxy_ob.get("streamSettings", {})
    network = str(stream.get("network", "xhttp")).lower()
    security = str(stream.get("security", "reality")).lower()
    
    reality = stream.get("realitySettings", {})
    tls_settings = stream.get("tlsSettings", {})
    
    sni = reality.get("serverName") or tls_settings.get("serverName") or "www.yahoo.com"
    public_key = reality.get("publicKey", "tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg")
    short_id = reality.get("shortId", "21569dd6")
    fingerprint = reality.get("fingerprint", "chrome")
    
    xhttp_settings = stream.get("xhttpSettings", {})
    path = xhttp_settings.get("path", "/OCrp5Ajs")
    mode = xhttp_settings.get("mode", "auto")

    is_ipv6 = ":" in server
    uri_server = f"[{server}]" if is_ipv6 else server

    # 1. 生成 Clash Meta (Mihomo) & Karing 字典
    clash_proxy = {
        "name": default_name,
        "type": "vless",
        "server": server,
        "port": port,
        "uuid": uuid,
        "udp": True,
        "tls": True,
        "flow": flow,
        "servername": sni,
        "client-fingerprint": fingerprint,
        "network": network,
        "reality-opts": {
            "public-key": public_key,
            "short-id": short_id
        }
    }
    
    if network == "xhttp":
        clash_proxy["xhttp-opts"] = {
            "path": path,
            "mode": mode
        }
    elif network == "ws":
        clash_proxy["ws-opts"] = {
            "path": path,
            "headers": {"Host": sni}
        }
    elif network == "grpc":
        clash_proxy["grpc-opts"] = {
            "grpc-service-name": stream.get("grpcSettings", {}).get("serviceName", "")
        }

    # 2. 生成标准 VLESS URI 链接 (携带加密参数)
    query_parts = [
        f"encryption={quote(encryption)}",
        f"security={quote(security)}",
        f"type={quote(network)}",
        f"pbk={quote(public_key)}",
        f"fp={quote(fingerprint)}",
        f"sni={quote(sni)}",
        f"sid={quote(short_id)}",
    ]
    if flow:
        query_parts.append(f"flow={quote(flow)}")
    if network == "xhttp":
        query_parts.append(f"path={quote(path)}")
        query_parts.append(f"mode={quote(mode)}")
    elif network == "ws":
        query_parts.append(f"path={quote(path)}")
    
    uri = f"vless://{uuid}@{uri_server}:{port}?" + "&".join(query_parts) + f"#{quote(default_name)}"

    # 3. 生成 Sing-Box 结构
    singbox_node = {
        "type": "vless",
        "tag": default_name,
        "server": server,
        "server_port": port,
        "uuid": uuid,
        "flow": flow,
        "tls": {
            "enabled": True,
            "server_name": sni,
            "utls": {
                "enabled": True,
                "fingerprint": fingerprint
            },
            "reality": {
                "enabled": True,
                "public_key": public_key,
                "short_id": short_id
            }
        }
    }
    if network == "xhttp":
        singbox_node["transport"] = {
            "type": "xhttp",
            "path": path,
            "mode": mode
        }

    return clash_proxy, uri, singbox_node

def dump_yaml_proxies(proxies):
    """序列化为 Clash Meta YAML"""
    lines = []
    for p in proxies:
        lines.append(f"  - name: \"{p['name']}\"")
        lines.append(f"    type: {p['type']}")
        lines.append(f"    server: \"{p['server']}\"")
        lines.append(f"    port: {p['port']}")
        lines.append(f"    uuid: \"{p['uuid']}\"")
        lines.append(f"    udp: true")
        lines.append(f"    tls: true")
        if p.get("flow"):
            lines.append(f"    flow: \"{p['flow']}\"")
        lines.append(f"    servername: \"{p.get('servername', 'www.yahoo.com')}\"")
        lines.append(f"    client-fingerprint: \"{p.get('client-fingerprint', 'chrome')}\"")
        lines.append(f"    network: {p.get('network', 'xhttp')}")
        
        if "reality-opts" in p:
            lines.append("    reality-opts:")
            lines.append(f"      public-key: \"{p['reality-opts'].get('public-key', '')}\"")
            lines.append(f"      short-id: \"{p['reality-opts'].get('short-id', '')}\"")
            
        if "xhttp-opts" in p:
            lines.append("    xhttp-opts:")
            lines.append(f"      path: \"{p['xhttp-opts'].get('path', '/OCrp5Ajs')}\"")
            lines.append(f"      mode: \"{p['xhttp-opts'].get('mode', 'auto')}\"")
            
    return "\n".join(lines)

def render_template(template_str, proxies):
    """渲染完整订阅配置"""
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
    print("🚀 开始运行 GitHub 真实上游 Xray (VLESS Reality) 提取与转换工作流")
    print("=" * 65)

    urls = extract_all_urls(URLS_FILE)
    print(f"[*] 从 urls.txt 成功提取到 {len(urls)} 个 URL 链接")

    all_clash_proxies = []
    all_uris = []
    all_singbox_nodes = []
    first_raw_json = None

    # 分别为 4 个节点序号生成独立节点（即使上游 IP 相同也保留 4 个订阅槽位）
    node_configs = {}
    for u in urls:
        m = re.search(r"/xray/(\d+)/", u)
        slot_idx = int(m.group(1)) if m else (len(node_configs) + 1)
        if slot_idx in node_configs:
            continue
        print(f"[*] 正在拉取 节点槽位 [{slot_idx}]: {u}")
        content = fetch_upstream_content(u)
        if content:
            node_configs[slot_idx] = content
            if not first_raw_json:
                try:
                    first_raw_json = json.loads(content)
                except Exception:
                    pass

    for slot_idx in sorted(node_configs.keys()):
        content = node_configs[slot_idx]
        slot_name = f"Xray-VLESS-{'IPv4' if slot_idx <= 2 else 'IPv6'}-0{slot_idx}"
        clash_p, uri, singbox_n = parse_xray_node(content, slot_name)
        if clash_p:
            all_clash_proxies.append(clash_p)
            all_uris.append(uri)
            all_singbox_nodes.append(singbox_n)
            print(f"  [√] 成功生成节点 {slot_name}: {clash_p['server']}:{clash_p['port']} (Network: {clash_p.get('network')}, SNI: {clash_p.get('servername')})")

    # 注入用户专属备用节点 (lovelive 备用线路)
    user_backup_json = """{
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "62.210.113.151",
          "port": 45641,
          "users": [{ "id": "f2d9e117-231c-4946-87d8-2cde2222b85d", "encryption": "mlkem768x25519plus.native.0rtt.zSYuX7pyA0rEd8VpVAxu72mLwTrKQuScjFWKPCaaMsKlB6CBmEllLAhj1mk37vQNJvma7Fs51ukzsqU3-honW3JM8cOiZNsxc-U3DJgbS8CZthsH4blkJlXEz6PPnGlrLQZozdkQ4oh5NeNE8uwYgdUFCnKyrhWKqGaM1JmbWgdFqpFqI5u0SDt_IdBdTxlptLa8MfW00Osz-jy74bW8DFq1vbJlQ0pLkNBdL-xCPMANIQY0yLsaFWN0uUp5pSWbc7XNRqHK2Xeuzvyw9px4HiBfG4q3VWXCL_hXr5NNHHQAjaBamSGI6ZIcE2RqgOGM-Ow3xPjBjvqBSeYzgYBMsBDP0sdRLrcAY6k6TZOlHNEgkxwgiMpXpYOuTGSsSLmuYxiIAH1DWJagU_NsJtVOZUKLtio263GFxXsJdVyBc_ACYEFheLBWBCUQBwYQIudfStHFQ2GCQaF64DOOrFcWacABMdY0qOIMPPyLVVJKjdF74OisuilVQmAs_bNIQ_CXnYkGJwlI_aVKJomFiHHOLkc5F2iiYdQuK4AaIumpqskx0MNxKotbyuxtA0MVRVucjmVyVOgR4TZfHirLoMWVxuKIwpddKyZtAeA_zDuuS_BJUEWMbmh_etVkRYhze7N17bfC1ruFTBZCdKUEeoVXiAcr_4kmLtKAP7TDDVMpmZlDC9KiZWKGLYSVteULYoHBgAWN_RKYawNOivkECYEO75ho2vJAVLqNF2KKyuMxZXdfKFbJfrscfFqWAMy08UDOH-sQGNZwVzEsebgw5wsaORGlTfm-9HwlYpYwfKIrJIwfj1uLSuMGHTWMnLeJPLIOsXJuWgKGSigV2sCDZrZWg2K5ZanMg1WpuzS9FjGMt8Z2ACNyd0ZM9NpoofeBLGcomZF_X3akPxG60Nt3lMBOkapRnRk5-ekNCfpmeKFfTcYIvQenR8FMxehQjPmG-kSJWGRL4efCeSSBBlNsdwyjZRsxeOwYAeRqHQlwBrYFgcoyrYmRW6yo5ocQPfAtqxq6VjiVM2ljxjOjK6Sy1QGSfUGA51WQA6BNrDyj_YcVCBkfdZBwHQmv6bTLKDZsFdY6FPmDOmsgM6MAxnEO6FuZQfcWb2Zm_zoTHhguW_oU7dsGEaKZ2Ns3Q5CAPYNRwDG5AI1Wh5VI-1ctFjpT8jtX3AC-46R7LkxUONddX8mHQ5BjKcwSNuDLOmOYRZm6ZrYHCYF6vXpZHNbIcdI5gUkxWANI8Hh2qTBuiQZ6t4qH2BGEsuwPAuZ6a3wzGmzCoTI-HyVAinhXohcsTjka62E7osQt11wTFnkVjBNGb-d-I4c6YRh31SRjnirG0esDWly7qcB3zEy0RMSshISKsNFRdeFfGPe4x5zD0cMvo4E3rQQ9xHJlckg4s5uCO4dk_cgcSeYHZZgADJErzIeRZpA9f-XBjNqdIFpnJAyzCMC9D2Msi8cXKys2kiJWiqyo1hAlr7YWEMC2JozJ7WlrNAFRmTsujSsdEvZoeECLmasq7eUvGmoMrFBsSIrBGXJBHdqzWx1z57id_4o81ihH0MA0yYW_67JZn7nFG0htFqUnyac" }]
        }]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": { "serverName": "www.lovelive-anime.jp", "fingerprint": "chrome", "publicKey": "Nw-FuuCWzFZvQtQbJjDCYJpCKyO8cuvibbTGBeoZRyo", "shortId": "1ea5bfb5" },
        "xhttpSettings": { "path": "/SSSuqkzN", "mode": "auto" }
      }
    }"""
    try:
        user_backup_dict = json.loads(user_backup_json)
        full_wrapped = {"outbounds": [user_backup_dict]}
        clash_u, uri_u, sing_u = parse_xray_node(json.dumps(full_wrapped), "Xray-VLESS-Backup-05")
        if clash_u:
            all_clash_proxies.append(clash_u)
            all_uris.append(uri_u)
            all_singbox_nodes.append(sing_u)
            print(f"  [√] 成功注入用户自定义备用节点: {clash_u['name']} ➔ {clash_u['server']}:{clash_u['port']}")
    except Exception as e:
        print(f"[!] 注入备用节点失败: {e}")

    print(f"\n[=] 总计成功生成 {len(all_clash_proxies)} 个完整 Xray 节点！")

    # 1. 写入明文链接 (xray_links.txt)
    uris_text = "\n".join(all_uris)
    with open(XRAY_LINKS_TXT, "w", encoding="utf-8") as f:
        f.write(uris_text + "\n")
    print(f"[√] 已写入 Xray URI 链接清单: {XRAY_LINKS_TXT}")

    # 2. 写入 Base64 通用订阅 (sub.txt & config.b64)
    b64_content = base64.b64encode(uris_text.encode("utf-8")).decode("utf-8") if uris_text else ""
    with open(SUB_OUTPUT, "w", encoding="utf-8") as f:
        f.write(b64_content + "\n")
    with open(CONFIG_B64, "w", encoding="utf-8") as f:
        f.write(b64_content + "\n")
    print(f"[√] 已写入 Base64 订阅: {SUB_OUTPUT}")

    # 3. 写入完整 Clash Meta / Karing 订阅 (config.yaml & clash.yaml)
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template_content = f.read()

        rendered_yaml = render_template(template_content, all_clash_proxies)
        with open(CONFIG_YAML, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        with open(CLASH_OUTPUT, "w", encoding="utf-8") as f:
            f.write(rendered_yaml)
        print(f"[√] 已写入完整 Clash Meta / Karing 订阅: {CONFIG_YAML}")

    # 4. 写入原生 Xray 客户端完整配置 (xray_config.json)
    try:
        xray_client_config = first_raw_json if first_raw_json else {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {"tag": "socks", "port": 1080, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True}},
                {"tag": "http", "port": 1081, "listen": "127.0.0.1", "protocol": "http", "settings": {"auth": "noauth"}}
            ],
            "outbounds": [
                {
                    "tag": "proxy",
                    "protocol": "vless",
                    "settings": {
                        "vnext": [{
                            "address": all_clash_proxies[0]["server"],
                            "port": all_clash_proxies[0]["port"],
                            "users": [{"id": all_clash_proxies[0]["uuid"]}]
                        }]
                    },
                    "streamSettings": {
                        "network": all_clash_proxies[0].get("network", "xhttp"),
                        "security": "reality",
                        "realitySettings": {
                            "serverName": all_clash_proxies[0].get("servername", "www.yahoo.com"),
                            "fingerprint": all_clash_proxies[0].get("client-fingerprint", "chrome"),
                            "publicKey": all_clash_proxies[0].get("reality-opts", {}).get("public-key", ""),
                            "shortId": all_clash_proxies[0].get("reality-opts", {}).get("short-id", "")
                        },
                        "xhttpSettings": {
                            "path": all_clash_proxies[0].get("xhttp-opts", {}).get("path", "/OCrp5Ajs"),
                            "mode": all_clash_proxies[0].get("xhttp-opts", {}).get("mode", "auto")
                        }
                    }
                },
                {"tag": "direct", "protocol": "freedom"},
                {"tag": "block", "protocol": "blackhole"}
            ]
        }
        with open(XRAY_CONFIG_JSON, "w", encoding="utf-8") as f:
            json.dump(xray_client_config, f, ensure_ascii=False, indent=2)
        print(f"[√] 已写入原生 Xray 客户端配置: {XRAY_CONFIG_JSON}")
    except Exception as e:
        print(f"[!] 生成 Xray JSON 失败: {e}")

    # 5. 写入 Sing-Box 格式配置 (singbox.json)
    try:
        with open(SINGBOX_OUTPUT, "w", encoding="utf-8") as f:
            json.dump({"outbounds": all_singbox_nodes}, f, ensure_ascii=False, indent=2)
        print(f"[√] 已写入 Sing-Box 格式: {SINGBOX_OUTPUT}")
    except Exception as e:
        print(f"[!] 生成 Sing-Box 失败: {e}")

    print("=" * 65)
    print(f"✨ 成功提取并生成 {len(all_clash_proxies)} 个完整 Xray 节点！")
    print("=" * 65)

if __name__ == "__main__":
    main()
