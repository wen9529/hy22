#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions 自动化转换脚本 (Xray VLESS Reality 智能提取版)：
1. 自动读取 urls.txt，精准提取全部 Xray URL 配置源 (支持 GitLab 与镜像源主备容灾)
2. 实时从 upstream 下载真实动态 Xray 配置：
   - 提取 VLESS + Reality + XHTTP / TCP 节点
   - 包含 IPv4 (62.210.70.194) 与 IPv6 节点
3. 完美兼容 Clash Meta (Mihomo)、Karing、v2rayN、Sing-Box 与 Shadowrocket：
   - 生成完整 Clash Meta 订阅 (config.yaml / clash.yaml)
   - 生成原生 Xray 客户端配置 (xray_config.json)
   - 生成标准 VLESS URI 明文清单 (xray_links.txt)
   - 生成 Base64 通用订阅 (sub.txt / config.b64)
   - 生成 Sing-Box 格式配置 (singbox.json)
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

# Clean up legacy hy2 artifacts if they exist
for legacy in ["hy2_config.yaml", "hy2_config.b64", "hy2_links.txt"]:
    legacy_path = os.path.join(BASE_DIR, legacy)
    if os.path.exists(legacy_path):
        try:
            os.remove(legacy_path)
        except Exception:
            pass

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
    """从真实 URL 动态下载最新的配置 (支持 JSON 与 YAML)"""
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
        print(f"  [-] 请求失败: {e}")
    return None

def parse_xray_node(content, default_name):
    """从 Xray config.json 中精准解析 VLESS Reality 节点"""
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
    
    # 查找主代理 outbound (protocol 为 vless / vmess / trojan 等)
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
    flow = ""
    
    if vnext and isinstance(vnext, list) and len(vnext) > 0:
        vn0 = vnext[0]
        server = str(vn0.get("address", server)).strip("[]")
        port = int(vn0.get("port", port))
        users = vn0.get("users", [])
        if users and len(users) > 0:
            uuid = str(users[0].get("id", uuid))
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

    # 2. 生成标准 VLESS URI 链接
    query_parts = [
        f"type={quote(network)}",
        f"security={quote(security)}",
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
    """将代理列表序列化为高兼容 YAML 格式 (完全兼容 Clash Meta 与 Karing)"""
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
    """渲染完整的 Clash Meta 策略组与分流规则"""
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

    seen_endpoints = set()

    for u in urls:
        print(f"[*] 正在处理: {u}")
        content = fetch_upstream_content(u)
        if not content:
            continue

        if not first_raw_json:
            try:
                first_raw_json = json.loads(content)
            except Exception:
                pass

        default_name = f"Xray-VLESS-{len(all_clash_proxies)+1:02d}"
        clash_p, uri, singbox_n = parse_xray_node(content, default_name)

        if clash_p:
            endpoint = f"{clash_p['server']}_{clash_p['port']}"
            if endpoint not in seen_endpoints:
                seen_endpoints.add(endpoint)
                is_v6 = ":" in clash_p["server"]
                clash_p["name"] = f"Xray-VLESS-{'IPv6' if is_v6 else 'IPv4'}-{len(all_clash_proxies)+1:02d}"
                singbox_n["tag"] = clash_p["name"]
                
                all_clash_proxies.append(clash_p)
                all_uris.append(uri)
                all_singbox_nodes.append(singbox_n)
                print(f"  [√] 成功解析 Xray 节点: {clash_p['name']} ➔ {clash_p['server']}:{clash_p['port']} (Network: {clash_p.get('network')}, SNI: {clash_p.get('servername')})")

    # 兜底默认备用节点 (确保无论网络状况如何均有完整节点)
    if not all_clash_proxies:
        print("[!] 上游临时未响应，注入标准稳定 VLESS 节点作为备用...")
        fallback_v4 = {
            "name": "Xray-VLESS-IPv4-01",
            "type": "vless",
            "server": "62.210.70.194",
            "port": 37783,
            "uuid": "a289c660-1b12-432b-a06c-c2ae469272b0",
            "udp": True,
            "tls": True,
            "flow": "",
            "servername": "www.yahoo.com",
            "client-fingerprint": "chrome",
            "network": "xhttp",
            "reality-opts": {
                "public-key": "tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg",
                "short-id": "21569dd6"
            },
            "xhttp-opts": {
                "path": "/OCrp5Ajs",
                "mode": "auto"
            }
        }
        all_clash_proxies.append(fallback_v4)
        uri_fallback = "vless://a289c660-1b12-432b-a06c-c2ae469272b0@62.210.70.194:37783?type=xhttp&security=reality&pbk=tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg&fp=chrome&sni=www.yahoo.com&sid=21569dd6&path=%2FOCrp5Ajs&mode=auto#Xray-VLESS-IPv4-01"
        all_uris.append(uri_fallback)
        all_singbox_nodes.append({
            "type": "vless",
            "tag": "Xray-VLESS-IPv4-01",
            "server": "62.210.70.194",
            "server_port": 37783,
            "uuid": "a289c660-1b12-432b-a06c-c2ae469272b0",
            "tls": {
                "enabled": True,
                "server_name": "www.yahoo.com",
                "utls": {"enabled": True, "fingerprint": "chrome"},
                "reality": {
                    "enabled": True,
                    "public_key": "tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg",
                    "short_id": "21569dd6"
                }
            },
            "transport": {"type": "xhttp", "path": "/OCrp5Ajs", "mode": "auto"}
        })

    print(f"\n[=] 总计成功生成 {len(all_clash_proxies)} 个真实 Xray VLESS 节点 (包含 IPv4 与 IPv6)")

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
    print("✨ Xray (VLESS Reality) 全套订阅生成完成！")
    print("=" * 65)

if __name__ == "__main__":
    main()
