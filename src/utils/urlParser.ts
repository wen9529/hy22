import { UrlItem } from '../types';

export function extractUrlsFromText(rawText: string): UrlItem[] {
  if (!rawText || !rawText.trim()) return [];

  // Match all HTTP/HTTPS URLs
  const urlRegex = /https?:\/\/[^\s"'`<>]+/g;
  const matches = rawText.match(urlRegex) || [];

  if (matches.length === 0) return [];

  // Clean URLs (strip trailing punctuation or quotes)
  const cleanedUrls = matches.map((u) => u.replace(/[,\s"')]+$/, '').trim());

  // Group by node identity (e.g. /hysteria2/(\d+)/ or similar path pattern)
  const nodeMap = new Map<string, { primary: string; fallback?: string; index?: number }>();
  const unkeyedUrls: string[] = [];

  for (const url of cleanedUrls) {
    // Check if URL contains pattern like /hysteria2/(\d+)/config.json or /node/(\d+)
    const patternMatch = url.match(/\/hysteria2\/(\d+)\//i) || url.match(/\/(\d+)\/config\.json/i);

    if (patternMatch) {
      const nodeNum = parseInt(patternMatch[1], 10);
      const key = `node_${nodeNum}`;
      if (!nodeMap.has(key)) {
        nodeMap.set(key, { primary: url, index: nodeNum });
      } else {
        const existing = nodeMap.get(key)!;
        if (!existing.fallback && existing.primary !== url) {
          existing.fallback = url;
        }
      }
    } else {
      unkeyedUrls.push(url);
    }
  }

  const items: UrlItem[] = [];

  // Add keyed nodes (sorted by index)
  const sortedEntries = Array.from(nodeMap.entries()).sort(
    (a, b) => (a[1].index ?? 0) - (b[1].index ?? 0)
  );

  for (const [key, val] of sortedEntries) {
    items.push({
      id: key,
      name: `Hysteria2-${String(val.index ?? items.length + 1).padStart(2, '0')}`,
      primaryUrl: val.primary,
      fallbackUrl: val.fallback,
      nodeIndex: val.index,
      protocol: 'hysteria2',
    });
  }

  // Add remaining unkeyed URLs
  let unkeyedCount = 1;
  const seenUnkeyed = new Set<string>();

  for (const url of unkeyedUrls) {
    if (seenUnkeyed.has(url)) continue;
    seenUnkeyed.add(url);

    const idx = items.length + 1;
    items.push({
      id: `url_${idx}`,
      name: `Node-${String(idx).padStart(2, '0')}`,
      primaryUrl: url,
      nodeIndex: idx,
      protocol: url.toLowerCase().includes('hysteria') ? 'hysteria2' : 'custom',
    });
    unkeyedCount++;
  }

  return items;
}

export const SAMPLE_BAT_CONTENT = `@echo off
setlocal
chcp 936 >nul
cd /d "%~dp0"
Title ip1 节点获取 hysteria2 配置文件
..\\..\\wget -t 2  --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/1/config.json

if exist config.json goto startcopy

..\\..\\wget -t 2  --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/1/config.json

if exist config.json goto startcopy

Title ip2 节点获取 hysteria2 配置文件
..\\..\\wget -t 2  --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/2/config.json

if exist config.json goto startcopy

..\\..\\wget -t 2  --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/2/config.json

if exist config.json goto startcopy

Title ip3 节点获取 hysteria2 配置文件
..\\..\\wget -t 2 --no-hsts  --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/3/config.json

if exist config.json goto startcopy

..\\..\\wget -t 2  --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/3/config.json

if exist config.json goto startcopy

Title ip4 节点获取 hysteria2 配置文件
..\\..\\wget -t 2  --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/4/config.json

if exist config.json goto startcopy

..\\..\\wget -t 2  --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/4/config.json
`;

export const SAMPLE_HYSTERIA2_JSON = {
  server: "www.838491.xyz:13377",
  auth: "dongtaiwang.com",
  bandwidth: {
    up: "11 mbps",
    down: "55 mbps",
  },
  tls: {
    sni: "www.838491.xyz",
    insecure: false,
  },
  quic: {
    initStreamReceiveWindow: 16777216,
    maxStreamReceiveWindow: 16777216,
    initConnReceiveWindow: 33554432,
    maxConnReceiveWindow: 33554432,
  },
  socks5: {
    listen: "127.0.0.1:1080",
  },
  transport: {
    udp: {
      hopInterval: "30s",
    },
  },
};
