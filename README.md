# 🚀 Xray (VLESS Reality) 节点自动提取与全端通用订阅生成器

本项目通过 **GitHub Actions** 自动化定时任务：
1. 从 `urls.txt` 批量提取 Xray (VLESS Reality) 节点配置；
2. 批量并发下载最新节点配置，当主线路 (`gitlab.com`) 超时或故障时自动切换至备用镜像源；
3. 输出 **全端通用的 Base64 订阅 (`sub.txt`)**、**Clash Meta 完整分流配置 (`config.yaml`)**、**原生 Xray 配置 (`xray_config.json`)** 以及 **Sing-Box 格式 (`singbox.json`)**；
4. 定时自动提交回本仓库并通过全球 jsDelivr CDN 极速分发，国内免翻墙直接拉取。

---

## 🌟 一键通用订阅链接 (所有客户端通用，无需切换)

为了避免在不同客户端之间寻找不同链接的麻烦，推荐使用以下 **通用全能订阅**：

### 1. 通用 Base64 标准订阅 (首选 ⭐ 推荐)
> **支持全平台客户端**：Karing、Shadowrocket (小火箭)、v2rayN (Windows)、v2rayNG (Android)、NekoBox、Sing-box 等。

```text
https://fastly.jsdelivr.net/gh/wen9529/hy22@main/sub.txt
```

### 2. 智能自适应全协议订阅 (自动识别客户端)
> **自动匹配客户端**：根据请求的客户端（Clash、Sing-box、Surge、小火箭等）自动下发最适配的格式。

```text
https://api.v1.mk/sub?target=auto&url=https://fastly.jsdelivr.net/gh/wen9529/hy22@main/sub.txt
```

### 3. Clash Meta (Mihomo) & Karing 完整规则分流订阅
> 包含节点选择、自动优选、负载均衡策略组与大陆直连分流规则。

```text
https://fastly.jsdelivr.net/gh/wen9529/hy22@main/config.yaml
```

---

## ⚡ 首次启用工作流 (10 秒快速开启)

GitHub 出于安全保护机制，不允许第三方应用直接向 `.github/workflows/` 目录推送文件（会提示 *Insufficient permissions to push workflow files*）。
我们已将工作流配置文件存放在 `workflows/update-nodes.yml`，您只需在 GitHub 网页上手动创建一次即可永久生效：

### 操作步骤：
1. 打开您的 GitHub 仓库：[wen9529/hy22](https://github.com/wen9529/hy22)；
2. 点击上方的 **Add file** ➔ 选择 **Create new file**；
3. 在文件名输入框输入：
   ```text
   .github/workflows/update-nodes.yml
   ```
4. 将本仓库中 `workflows/update-nodes.yml` 的代码复制粘贴进去；
5. 点击右上角绿色的 **Commit changes...** ➔ **Commit changes** 保存！

---

## ⚙️ 开启 Actions 读写权限 (必做)

1. 点击仓库上方的 **Settings** (设置)；
2. 点击左侧菜单 **Actions** ➔ **General**；
3. 滚动到底部的 **Workflow permissions**；
4. 选择 **Read and write permissions** (允许读写权限)；
5. 点击绿色 **Save** 保存。

保存后，工作流**每周会自动运行一次**，且**每次仓库有任何文件更新推送时也会立即触发更新**，您也可以在 **Actions** 页面点击 **Run workflow** 手动触发！
