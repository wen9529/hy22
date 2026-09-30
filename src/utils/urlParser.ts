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
  "dns": {
    "hosts": {
      "dns.google": ["8.8.8.8","8.8.4.4","2001:4860:4860::8888","2001:4860:4860::8844"],
      "dns.alidns.com": ["223.5.5.5","223.6.6.6","2400:3200::1","2400:3200:baba::1"],
      "one.one.one.one": ["1.1.1.1","1.0.0.1","2606:4700:4700::1111","2606:4700:4700::1001"],
      "cloudflare-dns.com": ["104.16.249.249","104.16.248.249","2606:4700::6810:f8f9","2606:4700::6810:f9f9"],
      "dot.pub": ["1.12.12.12","120.53.53.53"]
    },
    "servers": [
      { "address": "https://dns.alidns.com/dns-query", "domains": ["geosite:private"], "skipFallback": true },
      { "address": "223.5.5.5", "domains": ["full:dns.alidns.com","full:cloudflare-dns.com"], "skipFallback": true },
      "https://cloudflare-dns.com/dns-query"
    ]
  },
  "inbounds": [
    {
      "tag": "socks",
      "port": 1080,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "sniffing": { "enabled": true, "destOverride": ["http","tls"], "routeOnly": false },
      "settings": { "auth": "noauth", "udp": true }
    },
    {
      "tag": "http",
      "port": 1081,
      "listen": "127.0.0.1",
      "protocol": "http",
      "sniffing": { "enabled": true, "destOverride": ["http","tls"], "routeOnly": false },
      "settings": { "auth": "noauth" }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "62.210.113.151",
          "port": 45641,
          "users": [{
            "id": "f2d9e117-231c-4946-87d8-2cde2222b85d",
            "encryption": "mlkem768x25519plus.native.0rtt..."
          }]
        }]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "reality",
        "realitySettings": {
          "serverName": "www.lovelive-anime.jp",
          "fingerprint": "chrome",
          "publicKey": "Nw-FuuCWzFZvQtQbJjDCYJpCKyO8cuvibbTGBeoZRyo",
          "shortId": "1ea5bfb5"
        },
        "xhttpSettings": {
          "path": "/SSSuqkzN",
          "mode": "auto"
        }
      }
    },
    { "tag": "direct", "protocol": "freedom" },
    { "tag": "block", "protocol": "blackhole" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      { "type": "field", "outboundTag": "block", "ip": ["geoip:private"] },
      { "type": "field", "outboundTag": "direct", "domain": ["geosite:private"] },
      { "type": "field", "outboundTag": "proxy", "port": "0-65535" }
    ]
  }
}`;
