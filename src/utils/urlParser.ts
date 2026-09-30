import { UrlItem } from '../types';

export function extractUrlsFromText(rawText: string): UrlItem[] {
  if (!rawText || !rawText.trim()) return [];

  // Match all HTTP/HTTPS URLs
  const urlRegex = /https?:\/\/[^\s"'`<>]+/g;
  const matches = rawText.match(urlRegex) || [];

  if (matches.length === 0) return [];

  // Clean URLs (strip trailing punctuation or quotes)
  const cleanedUrls = matches.map((u) => u.replace(/[,\s"')]+$/, '').trim());

  const items: UrlItem[] = [];
  const seenUrls = new Set<string>();

  for (const url of cleanedUrls) {
    if (seenUrls.has(url)) continue;
    seenUrls.add(url);

    const idx = items.length + 1;
    items.push({
      id: `node_${idx}`,
      name: `Xray-VLESS-${String(idx).padStart(2, '0')}`,
      primaryUrl: url,
      nodeIndex: idx,
      protocol: 'vless',
    });
  }

  return items;
}

export const SAMPLE_BAT_CONTENT = `@echo off
setlocal
chcp 936 >nul
cd /d "%~dp0"
Title ip1 自动更新 Xray 节点

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/xray/1/config.json
if exist config.json goto startcopy

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/xray/1/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/xray/2/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/xray/2/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/xray/3/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/xray/3/config.json

..\\..\\wget -t 2 --no-hsts --no-check-certificate https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ip/xray/4/config.json
..\\..\\wget -t 2 --no-hsts --no-check-certificate https://www.67867867.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ip/xray/4/config.json
`;

export const SAMPLE_XRAY_JSON = `{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "tag": "socks",
      "port": 1080,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": { "auth": "noauth", "udp": true }
    },
    {
      "tag": "http",
      "port": 1081,
      "listen": "127.0.0.1",
      "protocol": "http",
      "settings": { "auth": "noauth" }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "62.210.70.194",
          "port": 37783,
          "users": [{
            "id": "a289c660-1b12-432b-a06c-c2ae469272b0"
          }]
        }]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": {
          "serverName": "www.yahoo.com",
          "fingerprint": "chrome",
          "publicKey": "tQeEamJmYVUUfjRLX7ETvMnPj4DrHzRhR5TI684oYgg",
          "shortId": "21569dd6"
        },
        "xhttpSettings": {
          "path": "/OCrp5Ajs",
          "mode": "auto"
        }
      }
    },
    { "tag": "direct", "protocol": "freedom" },
    { "tag": "block", "protocol": "blackhole" }
  ]
}`;
