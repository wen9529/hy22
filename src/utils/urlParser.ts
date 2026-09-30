import { UrlItem } from '../types';

export function extractUrlsFromText(rawText: string): UrlItem[] {
  if (!rawText || !rawText.trim()) return [];

  // Match all HTTP/HTTPS URLs
  const urlRegex = /https?:\/\/[^\s"'`<>]+/g;
  const matches = rawText.match(urlRegex) || [];

  if (matches.length === 0) return [];

  // Clean URLs (strip trailing punctuation or quotes)
  const cleanedUrls = matches.map((u) => u.replace(/[,\s"')]+$/, '').trim());

  // Return each URL as an individual node item (8 URLs = 8 nodes)
  const items: UrlItem[] = [];
  const seenUrls = new Set<string>();

  for (const url of cleanedUrls) {
    if (seenUrls.has(url)) continue;
    seenUrls.add(url);

    const idx = items.length + 1;
    items.push({
      id: `node_${idx}`,
      name: `Hysteria2-${String(idx).padStart(2, '0')}`,
      primaryUrl: url,
      nodeIndex: idx,
      protocol: 'hysteria2',
    });
  }

  return items;
}

export const SAMPLE_BAT_CONTENT = `@echo off
setlocal
chcp 936 >nul
cd /d "%~dp0"
Title ip1 自动更新 hysteria2 节点

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/1/config.json
if exist config.json goto startcopy

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/1/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/2/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/2/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/3/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/3/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/hysteria2/4/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/hysteria2/4/config.json
`;

export const SAMPLE_HYSTERIA2_JSON = `{
  "server": "62.210.70.191:22000",
  "auth": "dongtaiwang.com",
  "bandwidth": {
    "up": "11 mbps",
    "down": "55 mbps"
  },
  "tls": {
    "sni": "www.microsoft.com",
    "insecure": true
  },
  "quic": {
    "initStreamReceiveWindow": 16777216,
    "maxStreamReceiveWindow": 16777216,
    "initConnReceiveWindow": 33554432,
    "maxConnReceiveWindow": 33554432
  },
  "socks5": {
    "listen": "127.0.0.1:1080"
  },
  "transport": {
    "udp": {
      "hopInterval": "30s"
    }
  }
}`;
