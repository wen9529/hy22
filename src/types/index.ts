export interface UrlItem {
  id: string;
  name: string;
  primaryUrl: string;
  fallbackUrl?: string;
  nodeIndex?: number;
  protocol?: string;
}

export interface Hysteria2RawConfig {
  server?: string;
  auth?: string;
  bandwidth?: {
    up?: string;
    down?: string;
  };
  tls?: {
    sni?: string;
    insecure?: boolean;
    alpn?: string[];
  };
  quic?: {
    initStreamReceiveWindow?: number;
    maxStreamReceiveWindow?: number;
    initConnReceiveWindow?: number;
    maxConnReceiveWindow?: number;
  };
  socks5?: {
    listen?: string;
  };
  transport?: {
    udp?: {
      hopInterval?: string;
    };
  };
  obfs?: {
    type?: string;
    password?: string;
  };
  [key: string]: any;
}

export interface ClashProxyItem {
  name: string;
  type: string;
  server: string;
  port: number;
  password?: string;
  sni?: string;
  'skip-cert-verify'?: boolean;
  alpn?: string[];
  up?: string;
  down?: string;
  'hop-interval'?: number | string;
  ports?: string;
  obfs?: string;
  'obfs-password'?: string;
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

export interface WorkflowOptions {
  cronSchedule: string;
  workflowName: string;
  targetFileName: string;
  branchName: string;
  pythonVersion: string;
  includeSingBox: boolean;
  autoCommit: boolean;
  commitMessage: string;
}
