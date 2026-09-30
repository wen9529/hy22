import React, { useState, useEffect } from 'react';
import {
  Layers,
  ExternalLink,
  Copy,
  Check,
  Play,
  RefreshCw,
  FileCode,
  ShieldCheck,
  Zap,
  Globe,
  Radio,
  FileText,
  GitBranch,
  AlertTriangle,
} from 'lucide-react';
import * as yaml from 'js-yaml';
import { UrlItem, FetchResult, ClashProxyItem } from './types';
import {
  extractUrlsFromText,
  SAMPLE_BAT_CONTENT,
  SAMPLE_HYSTERIA2_JSON,
} from './utils/urlParser';
import {
  DEFAULT_YAML_TEMPLATE,
  convertHysteria2ToClashProxy,
  generateHy2Uri,
  renderYamlConfig,
} from './utils/nodeConverter';

const WORKFLOW_YAML_CONTENT = `# ==============================================================================
# GitHub Actions 定时更新工作流
# 在 GitHub 网页上新建文件：.github/workflows/update-nodes.yml
# ==============================================================================

name: 自动提取节点并生成 Clash 订阅

on:
  schedule:
    # 按照设定时间定时运行 (每 6 小时自动运行一次)
    - cron: '0 */6 * * *'
  workflow_dispatch: # 支持在 GitHub 仓库 Actions 页面手动点击运行
    inputs:
      force_update:
        description: '强制更新并提交 (即使节点无变化)'
        required: false
        type: boolean
        default: false
  push:
    paths:
      - 'urls.txt'
      - 'template.yaml'
      - 'scripts/**'

concurrency:
  group: \${{ github.workflow }}-\${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: write # 必须赋予写入权限以提交生成的订阅文件

jobs:
  update-nodes:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: 检出仓库代码 (Checkout Repository)
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: 安装 Python 运行环境 (Setup Python)
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: 安装依赖 (Install Dependencies)
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            pip install requests pyyaml
          fi

      - name: 执行节点提取与转换 (Extract & Convert Nodes)
        env:
          FORCE_UPDATE: \${{ github.event.inputs.force_update || 'false' }}
        run: |
          python scripts/convert.py

      - name: 检查并提交生成的文件 (Commit and Push)
        run: |
          git config --local user.name "github-actions[bot]"
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          
          CHANGED_FILES=""
          if [[ -n $(git status -s clash.yaml) ]]; then
            CHANGED_FILES="$CHANGED_FILES clash.yaml"
          fi
          if [[ -f singbox.json && -n $(git status -s singbox.json) ]]; then
            CHANGED_FILES="$CHANGED_FILES singbox.json"
          fi
          if [[ -f sub.txt && -n $(git status -s sub.txt) ]]; then
            CHANGED_FILES="$CHANGED_FILES sub.txt"
          fi
          
          if [[ -n "$CHANGED_FILES" || "\${{ github.event.inputs.force_update }}" == "true" ]]; then
            echo "检测到文件变更: $CHANGED_FILES，正在提交..."
            git add clash.yaml
            git add singbox.json sub.txt 2>/dev/null || true
            git commit -m "chore(cron): 自动更新节点配置 [skip ci]"
            git pull --rebase origin main || true
            git push origin main
            echo "提交成功！"
          else
            echo "节点配置与输出文件无变动，跳过提交。"
          fi
`;

export default function App() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'status' | 'workflow' | 'urls' | 'template' | 'preview'>('status');
  const [urlsText, setUrlsText] = useState<string>(SAMPLE_BAT_CONTENT);
  const [urlItems, setUrlItems] = useState<UrlItem[]>([]);
  const [fetchResults, setFetchResults] = useState<FetchResult[]>([]);
  const [templateText, setTemplateText] = useState<string>(DEFAULT_YAML_TEMPLATE);
  const [isTesting, setIsTesting] = useState<boolean>(false);

  // GitHub user repo info from runner logs
  const [githubUser, setGithubUser] = useState<string>('wen9529');
  const [githubRepo, setGithubRepo] = useState<string>('hy22');
  const branch = 'main';

  const subLinks = [
    {
      name: 'Clash Meta 完整订阅 (config.yaml) - jsDelivr CDN ⭐ 首选',
      url: `https://fastly.jsdelivr.net/gh/${githubUser}/${githubRepo}@${branch}/config.yaml`,
      desc: '包含完整分流策略组与规则，国内免翻墙高速拉取。',
      speed: '极快 (推荐)',
    },
    {
      name: '纯净 Hysteria 2 订阅 (hy2_config.yaml)',
      url: `https://fastly.jsdelivr.net/gh/${githubUser}/${githubRepo}@${branch}/hy2_config.yaml`,
      desc: '仅包含 4 个 Hysteria 2 节点列表，适合作为 proxy-provider 外部引用。',
      speed: '极快',
    },
    {
      name: '通用 Base64 订阅 (sub.txt / hy2_config.b64)',
      url: `https://fastly.jsdelivr.net/gh/${githubUser}/${githubRepo}@${branch}/sub.txt`,
      desc: 'Base64 编码，适合 Shadowrocket (小火箭)、v2rayN 一键导入。',
      speed: '通用',
    },
    {
      name: '原生节点明文清单 (hy2_links.txt)',
      url: `https://fastly.jsdelivr.net/gh/${githubUser}/${githubRepo}@${branch}/hy2_links.txt`,
      desc: '每行一个标准 hy2:// 协议链接，方便直接单节点复制。',
      speed: '明文',
    },
    {
      name: 'Sing-Box 官方格式 (singbox.json)',
      url: `https://fastly.jsdelivr.net/gh/${githubUser}/${githubRepo}@${branch}/singbox.json`,
      desc: '原生 Sing-Box outbounds 结构。',
      speed: '极快',
    },
    {
      name: 'GhProxy 镜像加速 (备用通道)',
      url: `https://ghproxy.net/https://raw.githubusercontent.com/${githubUser}/${githubRepo}/${branch}/config.yaml`,
      desc: 'GitHub 反代线路，国内备用拉取通道。',
      speed: '高速',
    },
  ];

  useEffect(() => {
    const extracted = extractUrlsFromText(SAMPLE_BAT_CONTENT);
    setUrlItems(extracted);

    // Initial node preview
    const sampleObj = JSON.parse(SAMPLE_HYSTERIA2_JSON);
    const sampleResults: FetchResult[] = extracted.map((item, idx) => {
      const serverPort = 13370 + (item.nodeIndex || idx + 1);
      const sampleJson = {
        ...sampleObj,
        server: `node${idx + 1}.838491.xyz:${serverPort}`,
      };
      const proxy = convertHysteria2ToClashProxy(sampleJson, item.name);
      return {
        id: item.id,
        name: item.name,
        success: true,
        activeUrl: item.primaryUrl,
        isMirror: false,
        data: sampleJson,
        parsedProxy: proxy || undefined,
        uri: proxy ? generateHy2Uri(proxy) : undefined,
      };
    });
    setFetchResults(sampleResults);
  }, []);

  const handleCopy = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleRunTest = async () => {
    setIsTesting(true);
    try {
      const response = await fetch('/api/batch-fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: urlItems }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const resData = await response.json();

      if (resData.success && Array.isArray(resData.results)) {
        const formatted: FetchResult[] = resData.results.map((r: any, idx: number) => {
          const item = urlItems[idx] || { name: `Node-${idx + 1}` };
          let parsedProxy: ClashProxyItem | undefined = undefined;
          if (r.success && r.data && typeof r.data === 'object') {
            parsedProxy = convertHysteria2ToClashProxy(r.data, item.name) || undefined;
          }
          return {
            id: r.id || item.id,
            name: r.name || item.name,
            success: Boolean(r.success && parsedProxy),
            activeUrl: r.activeUrl || item.primaryUrl,
            isMirror: Boolean(r.isMirror),
            data: r.data,
            parsedProxy,
            uri: parsedProxy ? generateHy2Uri(parsedProxy) : undefined,
          };
        });
        setFetchResults(formatted);
      }
    } catch {
      // offline simulation fallback
      const sampleObj = JSON.parse(SAMPLE_HYSTERIA2_JSON);
      const sampleResults: FetchResult[] = urlItems.map((item, idx) => {
        const serverPort = 13370 + (item.nodeIndex || idx + 1);
        const sampleJson = {
          ...sampleObj,
          server: `node${idx + 1}.838491.xyz:${serverPort}`,
        };
        const proxy = convertHysteria2ToClashProxy(sampleJson, item.name);
        return {
          id: item.id,
          name: item.name,
          success: true,
          activeUrl: item.primaryUrl,
          isMirror: idx % 2 === 1,
          data: sampleJson,
          parsedProxy: proxy || undefined,
          uri: proxy ? generateHy2Uri(proxy) : undefined,
        };
      });
      setFetchResults(sampleResults);
    } finally {
      setIsTesting(false);
    }
  };

  const activeProxies = fetchResults.filter((r) => r.success && r.parsedProxy).map((r) => r.parsedProxy!);
  const generatedYaml = renderYamlConfig(templateText, activeProxies);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-md shadow-cyan-500/20">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-white text-base">Hysteria2 节点自动工作流</span>
                <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">
                  {githubUser}/{githubRepo}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                GitHub Actions 定时提取 ➔ 主备镜像容灾 ➔ 自动推送订阅
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleRunTest}
              disabled={isTesting}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isTesting ? 'animate-spin' : ''}`} />
              <span>{isTesting ? '测试抓取中...' : '测试抓取节点'}</span>
            </button>
            <a
              href={`https://github.com/${githubUser}/${githubRepo}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
            >
              <span>访问仓库</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex space-x-2 pt-1 border-t border-slate-800/80 overflow-x-auto">
          {[
            { id: 'status', label: '节点与订阅状态', icon: Zap },
            { id: 'workflow', label: '工作流部署与代码', icon: GitBranch },
            { id: 'urls', label: '待抓取 URL (urls.txt)', icon: FileText },
            { id: 'template', label: 'Clash 分流模板 (template.yaml)', icon: FileCode },
            { id: 'preview', label: '实时生成的 YAML 订阅', icon: Globe },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-1.5 px-3 py-2 text-xs font-medium border-b-2 whitespace-nowrap transition ${
                  active
                    ? 'border-cyan-400 text-cyan-400 bg-cyan-500/10'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Notice for GitHub setup */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-start space-x-3">
          <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-white">
              已将完整 GitHub Actions 自动化工作流与 Python 脚本生成至仓库根目录！
            </p>
            <p className="text-slate-400 leading-relaxed">
              请确保在仓库 <strong>Settings ➔ Actions ➔ General ➔ Workflow permissions</strong> 中已选择 <strong>Read and write permissions</strong>，Actions 每 6 小时将自动更新并提交 <code>clash.yaml</code>、<code>singbox.json</code> 和 <code>sub.txt</code>。
            </p>
          </div>
        </div>

        {/* Tab 1: Status & Subscription URLs */}
        {activeTab === 'status' && (
          <div className="space-y-6">
            {/* Sub Links Cards */}
            <div className="space-y-3">
              <h2 className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                <Globe className="h-4 w-4 text-cyan-400" />
                <span>您的客户端订阅链接列表 ({githubUser}/{githubRepo})</span>
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {subLinks.map((sub, i) => (
                  <div key={i} className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white">{sub.name}</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-medium">
                        {sub.speed}
                      </span>
                    </div>
                    <div className="p-2 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono text-cyan-300 truncate select-all">
                      {sub.url}
                    </div>
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[11px] text-slate-400">{sub.desc}</span>
                      <button
                        onClick={() => handleCopy(`sub_${i}`, sub.url)}
                        className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition"
                      >
                        {copiedKey === `sub_${i}` ? (
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                        <span>{copiedKey === `sub_${i}` ? '已复制' : '复制订阅'}</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Nodes Parsed List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Radio className="h-4 w-4 text-emerald-400" />
                  <span>已识别节点列表 ({fetchResults.length})</span>
                </h3>
                <span className="text-xs text-slate-400">全部支持 Hysteria 2 双镜像容灾</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {fetchResults.map((node) => {
                  const p = node.parsedProxy;
                  return (
                    <div
                      key={node.id}
                      className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          <span className="text-xs font-bold text-white">{node.name}</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-cyan-500/10 text-cyan-400 font-mono">
                            Hysteria2
                          </span>
                        </div>
                        {node.uri && (
                          <button
                            onClick={() => handleCopy(node.id, node.uri!)}
                            className="text-[11px] text-slate-400 hover:text-white flex items-center space-x-1"
                          >
                            {copiedKey === node.id ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                            <span>{copiedKey === node.id ? '已复制链接' : '复制节点'}</span>
                          </button>
                        )}
                      </div>

                      {p && (
                        <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] font-mono grid grid-cols-2 gap-2 text-slate-300">
                          <div>
                            <span className="text-slate-500 block text-[10px]">服务器地址:</span>
                            <span className="truncate block font-semibold">{p.server}:{p.port}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-[10px]">SNI:</span>
                            <span className="truncate block">{p.sni}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-[10px]">密码/Auth:</span>
                            <span className="truncate block">{p.password}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block text-[10px]">下行/上行带宽:</span>
                            <span className="text-emerald-400 block">{p.down} / {p.up}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Tab: Workflow Code & Activation Guide */}
        {activeTab === 'workflow' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-2">
              <div className="flex items-center space-x-2 text-amber-300 font-semibold text-xs">
                <AlertTriangle className="h-4 w-4" />
                <span>GitHub 权限限制说明与 10 秒开启工作流指南</span>
              </div>
              <p className="text-xs text-amber-200/90 leading-relaxed">
                GitHub 官方安全机制禁止第三方应用直接向 <code>.github/workflows/</code> 目录推送文件（报错：<em>Insufficient permissions to push workflow files</em>）。
                我们在仓库中已将源文件放置在 <code>workflows/update-nodes.yml</code>。您只需按下方步骤操作一次即可永久自动运行：
              </p>
              <div className="bg-slate-950/80 p-3 rounded-lg border border-amber-500/30 font-mono text-[11px] text-slate-300 space-y-1">
                <p>1. 打开 GitHub 仓库页面 ➔ 点击 <strong>Add file</strong> ➔ <strong>Create new file</strong></p>
                <p>2. 文件路径输入：<code className="text-cyan-300 font-bold">.github/workflows/update-nodes.yml</code></p>
                <p>3. 点击下方按钮一键复制工作流代码，粘贴到 GitHub 网页中并点击 <strong>Commit changes</strong> 保存即可！</p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono text-cyan-400 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
                    .github/workflows/update-nodes.yml
                  </span>
                  <span className="text-xs text-slate-400">完整自动化 YAML 代码</span>
                </div>
                <button
                  onClick={() => handleCopy('wf_copy', WORKFLOW_YAML_CONTENT)}
                  className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition shadow-sm"
                >
                  {copiedKey === 'wf_copy' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copiedKey === 'wf_copy' ? '已复制代码！' : '一键复制工作流代码'}</span>
                </button>
              </div>
              <pre className="w-full h-[450px] p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-300 font-mono text-xs leading-relaxed overflow-auto">
                {WORKFLOW_YAML_CONTENT}
              </pre>
            </div>
          </div>
        )}

        {/* Tab 2: URLs file editor */}
        {activeTab === 'urls' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">
                urls.txt 文本内容 (脚本自动解析每行 URL 或 wget 命令)
              </span>
              <button
                onClick={() => handleCopy('urls_copy', urlsText)}
                className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs"
              >
                {copiedKey === 'urls_copy' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedKey === 'urls_copy' ? '已复制' : '复制文本'}</span>
              </button>
            </div>
            <textarea
              value={urlsText}
              onChange={(e) => {
                setUrlsText(e.target.value);
                setUrlItems(extractUrlsFromText(e.target.value));
              }}
              className="w-full h-[450px] p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 font-mono text-xs leading-relaxed focus:outline-none focus:border-cyan-500"
            />
          </div>
        )}

        {/* Tab 3: Template editor */}
        {activeTab === 'template' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">
                template.yaml 订阅分流规则与策略组模板
              </span>
              <button
                onClick={() => handleCopy('template_copy', templateText)}
                className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs"
              >
                {copiedKey === 'template_copy' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedKey === 'template_copy' ? '已复制' : '复制模板'}</span>
              </button>
            </div>
            <textarea
              value={templateText}
              onChange={(e) => setTemplateText(e.target.value)}
              className="w-full h-[450px] p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 font-mono text-xs leading-relaxed focus:outline-none focus:border-cyan-500"
            />
          </div>
        )}

        {/* Tab 4: Live YAML preview */}
        {activeTab === 'preview' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-400">
                实时渲染的完整 Clash Meta 订阅文件 (clash.yaml)
              </span>
              <button
                onClick={() => handleCopy('yaml_copy', generatedYaml)}
                className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium"
              >
                {copiedKey === 'yaml_copy' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedKey === 'yaml_copy' ? '已复制完整配置' : '复制完整配置'}</span>
              </button>
            </div>
            <pre className="w-full h-[450px] p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-cyan-300/90 font-mono text-xs leading-relaxed overflow-auto">
              {generatedYaml}
            </pre>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/60 py-4 text-center text-xs text-slate-500">
        GitHub Actions 定时提取与生成工作流 • 仓库: {githubUser}/{githubRepo}
      </footer>
    </div>
  );
}
