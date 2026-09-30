import * as yaml from 'js-yaml';
import { ClashProxyItem, XrayRawConfig } from '../types';

/**
 * Converts raw Xray JSON config to Clash Meta (Mihomo) VLESS proxy item
 */
export function convertXrayToClashProxy(
  rawJson: XrayRawConfig | any,
  nodeName: string
): ClashProxyItem | null {
  if (!rawJson) return null;

  const outbounds = rawJson.outbounds || [];
  let proxyOb = outbounds.find((ob: any) =>
    ['vless', 'vmess', 'trojan', 'shadowsocks'].includes(String(ob.protocol || '').toLowerCase())
  );

  if (!proxyOb && outbounds.length > 0) {
    proxyOb = outbounds[0];
  }

  if (!proxyOb) return null;

  const proto = String(proxyOb.protocol || 'vless').toLowerCase();
  const settings = proxyOb.settings || {};
  const vnext = settings.vnext || [];

  let server = '62.210.70.194';
  let port = 37783;
  let uuid = 'a289c660-1b12-432b-a06c-c2ae469272b0';
  let flow = '';

  if (vnext.length > 0) {
    const vn0 = vnext[0];
    server = String(vn0.address || server).replace(/[\[\]]/g, '');
    port = parseInt(String(vn0.port || port), 10);
    const users = vn0.users || [];
    if (users.length > 0) {
      uuid = String(users[0].id || uuid);
      flow = String(users[0].flow || '');
    }
  }

  const stream = proxyOb.streamSettings || {};
  const network = String(stream.network || 'xhttp').toLowerCase();
  const security = String(stream.security || 'reality').toLowerCase();

  const reality = stream.realitySettings || {};
  const tls = stream.tlsSettings || {};

  const sni = reality.serverName || tls.serverName || 'www.yahoo.com';
  const publicKey = reality.publicKey || 'tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg';
  const shortId = reality.shortId || '21569dd6';
  const fingerprint = reality.fingerprint || 'chrome';

  const xhttp = stream.xhttpSettings || {};
  const path = xhttp.path || '/OCrp5Ajs';
  const mode = xhttp.mode || 'auto';

  const proxy: ClashProxyItem = {
    name: nodeName,
    type: 'vless',
    server: server,
    port: port,
    uuid: uuid,
    udp: true,
    tls: true,
    flow: flow || undefined,
    servername: sni,
    'client-fingerprint': fingerprint,
    network: network,
    'reality-opts': {
      'public-key': publicKey,
      'short-id': shortId,
    },
  };

  if (network === 'xhttp') {
    proxy['xhttp-opts'] = {
      path: path,
      mode: mode,
    };
  } else if (network === 'ws') {
    proxy['ws-opts'] = {
      path: path,
      headers: { Host: sni },
    };
  } else if (network === 'grpc') {
    proxy['grpc-opts'] = {
      'grpc-service-name': stream.grpcSettings?.serviceName || '',
    };
  }

  return proxy;
}

/**
 * Generate vless:// standard URI link
 */
export function generateVlessUri(proxy: ClashProxyItem): string {
  const uuid = proxy.uuid || 'a289c660-1b12-432b-a06c-c2ae469272b0';
  const hostStr = proxy.server.includes(':') && !proxy.server.startsWith('[')
    ? `[${proxy.server}]`
    : proxy.server;
  const tag = encodeURIComponent(proxy.name);
  const net = encodeURIComponent(proxy.network || 'xhttp');
  const sni = encodeURIComponent(proxy.servername || 'www.yahoo.com');
  const pbk = encodeURIComponent(proxy['reality-opts']?.['public-key'] || '');
  const sid = encodeURIComponent(proxy['reality-opts']?.['short-id'] || '');
  const fp = encodeURIComponent(proxy['client-fingerprint'] || 'chrome');

  const queryParts = [
    `type=${net}`,
    `security=reality`,
    `pbk=${pbk}`,
    `fp=${fp}`,
    `sni=${sni}`,
    `sid=${sid}`,
  ];

  if (proxy.flow) {
    queryParts.push(`flow=${encodeURIComponent(proxy.flow)}`);
  }
  if (proxy['xhttp-opts']?.path) {
    queryParts.push(`path=${encodeURIComponent(proxy['xhttp-opts'].path)}`);
    queryParts.push(`mode=${encodeURIComponent(proxy['xhttp-opts'].mode || 'auto')}`);
  }

  return `vless://${uuid}@${hostStr}:${proxy.port}?${queryParts.join('&')}#${tag}`;
}

/**
 * Convert proxy list to Sing-box outbound JSON format
 */
export function convertToSingboxOutbounds(proxies: ClashProxyItem[]) {
  return proxies.map((p) => {
    const node: any = {
      type: 'vless',
      tag: p.name,
      server: p.server,
      server_port: p.port,
      uuid: p.uuid,
      tls: {
        enabled: true,
        server_name: p.servername || 'www.yahoo.com',
        utls: {
          enabled: true,
          fingerprint: p['client-fingerprint'] || 'chrome',
        },
        reality: {
          enabled: true,
          public_key: p['reality-opts']?.['public-key'] || '',
          short_id: p['reality-opts']?.['short-id'] || '',
        },
      },
    };

    if (p.network === 'xhttp') {
      node.transport = {
        type: 'xhttp',
        path: p['xhttp-opts']?.path || '/OCrp5Ajs',
        mode: p['xhttp-opts']?.mode || 'auto',
      };
    }
    return node;
  });
}

/**
 * Default Mihomo / Clash Meta YAML Template
 */
export const DEFAULT_YAML_TEMPLATE = `# -------------------------------------------------------------
# Clash Meta (Mihomo) & Karing 自动订阅配置 (全端高兼容完美版)
# 自动生成时间: {{generated_time}}
# 节点数量: {{node_count}}
# -------------------------------------------------------------
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
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
    - 1.1.1.1
    - 8.8.8.8
    - 2400:3200::1

# 节点配置列表 (自动注入完整参数)
proxies:
{{proxies}}

# 策略组配置
proxy-groups:
  - name: 🚀 节点选择
    type: select
    proxies:
      - ♻️ 自动选择
      - ⚖️ 负载均衡
      - DIRECT
{{proxy_names_indented}}

  - name: ♻️ 自动选择
    type: url-test
    url: http://www.gstatic.com/generate_204
    interval: 300
    tolerance: 50
    proxies:
{{proxy_names_indented}}

  - name: ⚖️ 负载均衡
    type: load-balance
    strategy: consistent-hashing
    url: http://www.gstatic.com/generate_204
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
  - GEOIP,LAN,DIRECT,no-resolve
  - GEOIP,CN,DIRECT
  - MATCH,🚀 节点选择
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

  const indentedProxies = proxiesYaml
    .split('\n')
    .filter((line) => line.trim().length > 0)
    .map((line) => `  ${line}`)
    .join('\n');

  const proxyNamesIndented = proxies
    .map((p) => `      - "${p.name}"`)
    .join('\n');

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
