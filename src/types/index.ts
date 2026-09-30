export interface UrlItem {
  id: string;
  name: string;
  primaryUrl: string;
  fallbackUrl?: string;
  nodeIndex?: number;
  protocol?: string;
}

export interface XrayOutboundConfig {
  tag?: string;
  protocol?: string;
  settings?: {
    vnext?: Array<{
      address?: string;
      port?: number;
      users?: Array<{
        id?: string;
        encryption?: string;
        flow?: string;
      }>;
    }>;
  };
  streamSettings?: {
    network?: string;
    security?: string;
    realitySettings?: {
      serverName?: string;
      fingerprint?: string;
      publicKey?: string;
      shortId?: string;
      spiderX?: string;
    };
    tlsSettings?: {
      serverName?: string;
      allowInsecure?: boolean;
    };
    xhttpSettings?: {
      path?: string;
      mode?: string;
    };
    wsSettings?: {
      path?: string;
      headers?: Record<string, string>;
    };
    grpcSettings?: {
      serviceName?: string;
    };
  };
  [key: string]: any;
}

export interface XrayRawConfig {
  log?: { loglevel?: string };
  dns?: any;
  inbounds?: any[];
  outbounds?: XrayOutboundConfig[];
  routing?: any;
  [key: string]: any;
}

export interface ClashProxyItem {
  name: string;
  type: string;
  server: string;
  port: number;
  uuid?: string;
  password?: string;
  udp?: boolean;
  tls?: boolean;
  flow?: string;
  servername?: string;
  'client-fingerprint'?: string;
  network?: string;
  'reality-opts'?: {
    'public-key'?: string;
    'short-id'?: string;
  };
  'xhttp-opts'?: {
    path?: string;
    mode?: string;
  };
  'ws-opts'?: {
    path?: string;
    headers?: Record<string, string>;
  };
  'grpc-opts'?: {
    'grpc-service-name'?: string;
  };
  sni?: string;
  'skip-cert-verify'?: boolean;
  alpn?: string[];
  [key: string]: any;
}

export interface FetchResult {
  id: string;
  name: string;
  success: boolean;
  activeUrl?: string;
  isMirror?: boolean;
  data?: any;
  error?: string;
  parsedProxy?: ClashProxyItem;
  uri?: string;
  latencyMs?: number;
}
