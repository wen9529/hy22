import * as yaml from 'js-yaml';
import { ClashProxyItem, Hysteria2RawConfig } from '../types';

/**
 * Converts raw Hysteria2 JSON config to Clash Meta (Mihomo) proxy item
 */
export function convertHysteria2ToClashProxy(
  rawJson: Hysteria2RawConfig,
  nodeName: string
): ClashProxyItem | null {
  if (!rawJson) return null;

  let host = '';
  let port = 443;

  if (rawJson.server) {
    // Check if server is "domain:port" or "[ipv6]:port"
    if (rawJson.server.startsWith('[')) {
      const v6Match = rawJson.server.match(/^\[(.*?)\]:?(\d+)?$/);
      if (v6Match) {
        host = v6Match[1];
        if (v6Match[2]) port = parseInt(v6Match[2], 10);
      } else {
        host = rawJson.server;
      }
    } else if (rawJson.server.includes(':')) {
      const parts = rawJson.server.split(':');
      host = parts[0];
      port = parseInt(parts[1], 10) || 443;
    } else {
      host = rawJson.server;
      if (rawJson.port) port = parseInt(rawJson.port, 10);
    }
  }

  if (!host) {
    return null;
  }

  const password = rawJson.auth || '';
  const sni = rawJson.tls?.sni || host;
  const insecure = Boolean(rawJson.tls?.insecure);
  const up = rawJson.bandwidth?.up || '15 mbps';
  const down = rawJson.bandwidth?.down || '60 mbps';

  const proxy: ClashProxyItem = {
    name: nodeName,
    type: 'hysteria2',
    server: host,
    port: port,
    password: password,
    sni: sni,
    'skip-cert-verify': insecure,
    alpn: rawJson.tls?.alpn || ['h3'],
    up: up,
    down: down,
  };

  if (rawJson.transport?.udp?.hopInterval) {
    const hop = parseInt(rawJson.transport.udp.hopInterval, 10);
    if (!isNaN(hop) && hop > 0) {
      proxy['hop-interval'] = hop;
    }
  }

  if (rawJson.obfs?.type) {
    proxy.obfs = rawJson.obfs.type;
    if (rawJson.obfs.password) {
      proxy['obfs-password'] = rawJson.obfs.password;
    }
  }

  return proxy;
}

/**
 * Generate hy2:// link
 */
export function generateHy2Uri(proxy: ClashProxyItem): string {
  const pwd = encodeURIComponent(proxy.password || '');
  const sni = encodeURIComponent(proxy.sni || proxy.server);
  const tag = encodeURIComponent(proxy.name);
  const insecure = proxy['skip-cert-verify'] ? '1' : '0';
  const hostStr = proxy.server.includes(':') && !proxy.server.startsWith('[')
    ? `[${proxy.server}]`
    : proxy.server;
  return `hy2://${pwd}@${hostStr}:${proxy.port}/?sni=${sni}&insecure=${insecure}#${tag}`;
}

/**
 * Convert proxy list to Sing-box outbound JSON format
 */
export function convertToSingboxOutbounds(proxies: ClashProxyItem[]) {
  return proxies.map((p) => {
    // Parse Mbps numbers
    const upNum = parseInt(String(p.up || '20'), 10) || 20;
    const downNum = parseInt(String(p.down || '60'), 10) || 60;

    return {
      type: 'hysteria2',
      tag: p.name,
      server: p.server,
      server_port: p.port,
      password: p.password || '',
      tls: {
        enabled: true,
        server_name: p.sni || p.server,
        insecure: Boolean(p['skip-cert-verify']),
        alpn: p.alpn || ['h3'],
      },
      up_mbps: upNum,
      down_mbps: downNum,
    };
  });
}

/**
 * Default Mihomo / Clash Meta YAML Template
 */
export const DEFAULT_YAML_TEMPLATE = `# -------------------------------------------------------------
# Clash Meta (Mihomo) 自动订阅配置 (双栈 IPv4 / IPv6 全面优化版)
# 自动生成时间: {{generated_time}}
# 节点数量: {{node_count}}
# -------------------------------------------------------------
port: 7890
socks-port: 7891
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
ipv6: true
unified-delay: true
tcp-concurrent: true
external-controller: 127.0.0.1:9090

dns:
  enable: true
  ipv6: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
    - 1.1.1.1
    - 8.8.8.8
    - 2400:3200::1
    - 2606:4700:4700::1111

# 节点配置列表 (自动注入)
proxies:
{{proxies}}

# 策略组配置
proxy-groups:
  - name: 🚀 节点选择
    type: select
    proxies:
      - ♻️ 自动选择
      - ⚖️ 负载均衡
{{proxy_names_indented}}
      - DIRECT

  - name: ♻️ 自动选择
    type: url-test
    url: https://www.gstatic.com/generate_204
    interval: 300
    tolerance: 50
    proxies:
{{proxy_names_indented}}

  - name: ⚖️ 负载均衡
    type: load-balance
    strategy: consistent-hashing
    url: https://www.gstatic.com/generate_204
    interval: 300
    proxies:
{{proxy_names_indented}}

  - name: 🎯 全球直连
    type: select
    proxies:
      - DIRECT
      - 🚀 节点选择

  - name: 🐟 漏网之鱼
    type: select
    proxies:
      - 🚀 节点选择
      - 🎯 全球直连

# 分流规则
rules:
  - GEOSITE,private,🎯 全球直连
  - GEOIP,private,🎯 全球直连,no-resolve
  - GEOSITE,category-games@cn,🎯 全球直连
  - GEOSITE,cn,🎯 全球直连
  - GEOIP,CN,🎯 全球直连
  - MATCH,🐟 漏网之鱼
`;

/**
 * Renders YAML using template and proxy items
 */
export function renderYamlConfig(
  templateContent: string,
  proxies: ClashProxyItem[]
): string {
  if (proxies.length === 0) {
    return templateContent
      .replace('{{proxies}}', '  # 暂无可用节点\n')
      .replace(/\{\{proxy_names_indented\}\}/g, '      - DIRECT')
      .replace('{{node_count}}', '0')
      .replace('{{generated_time}}', new Date().toISOString());
  }

  // Format proxies as clean YAML block
  const proxiesYaml = yaml.dump(proxies, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });

  // Indent each proxy line by 2 spaces to align under "proxies:"
  const indentedProxies = proxiesYaml
    .split('\n')
    .filter((line) => line.trim().length > 0)
    .map((line) => `  ${line}`)
    .join('\n');

  // Format proxy names indented (6 spaces) for proxy-groups
  const proxyNamesIndented = proxies
    .map((p) => `      - "${p.name}"`)
    .join('\n');

  // Plain names list
  const proxyNamesList = proxies
    .map((p) => `  - "${p.name}"`)
    .join('\n');

  let result = templateContent
    .replace('{{proxies}}', indentedProxies)
    .replace(/\{\{proxy_names_indented\}\}/g, proxyNamesIndented)
    .replace(/\{\{proxy_names\}\}/g, proxyNamesList)
    .replace('{{node_count}}', String(proxies.length))
    .replace('{{generated_time}}', new Date().toLocaleString('zh-CN', { hour12: false }));

  return result;
}
