# 🚀 Hysteria2 节点自动提取与 Clash / Sing-box 订阅生成器

本项目通过 **GitHub Actions** 自动化定时任务：
1. 从 `urls.txt` 批量提取 Hysteria2 节点 JSON 链接；
2. 批量并发下载最新节点配置，当主线路 (`gitlab.com`) 超时或故障时自动切换至备用镜像 (`67867867.xyz`)；
3. 将节点配置按照 `template.yaml` 渲染并生成带有分流策略组的完整 Clash Meta (Mihomo) 订阅文件；
4. 同时输出 `singbox.json` (Sing-box) 与 `sub.txt` (Base64 通用订阅)；
5. 定时自动提交回本仓库，客户端直接订阅即可，无需人工干预。

---

## ⚡ 首次启用工作流 (10 秒快速开启)

GitHub 出于安全保护机制，不允许第三方应用直接推送 `.github/workflows/` 目录。
我们已将工作流配置文件存放在 `workflows/update-nodes.yml`，您只需在 GitHub 上将其创建到 `.github/workflows/` 下：

### 操作步骤：
1. 打开您的 GitHub 仓库：[wen9529/hy2](https://github.com/wen9529/hy2)；
2. 点击上方的 **Add file** ➔ 选择 **Create new file**；
3. 在文件名输入框输入：
   ```text
   .github/workflows/update-nodes.yml
   ```
4. 将本仓库中 `workflows/update-nodes.yml` 的内容直接粘贴进去；
5. 点击右上角绿色的 **Commit changes...** ➔ **Commit changes** 保存！

---

## ⚙️ 开启 Actions 写入权限 (必做)

1. 点击仓库上方的 **Settings** (设置)；
2. 点击左侧菜单 **Actions** ➔ **General**；
3. 滚动到底部的 **Workflow permissions**；
4. 选择 **Read and write permissions** (允许读写权限)；
5. 点击绿色 **Save** 保存。

保存后，点击仓库顶部的 **Actions** 标签 ➔ 选择 **自动提取节点并生成 Clash 订阅** ➔ 点击 **Run workflow** 即可立即触发第一次自动更新！

---

## 🔗 免翻墙订阅链接 (直接复制填入客户端)

本仓库为公开 (Public) 仓库，国内可直接使用 **jsDelivr 全球免费 CDN** 进行高速拉取，更新无需科学上网：

### 1. Clash Meta / Mihomo 订阅 (推荐)
- **jsDelivr CDN 高速链接 (国内免翻墙首选 ⭐)**:
  ```text
  https://fastly.jsdelivr.net/gh/wen9529/hy2@main/clash.yaml
  ```
- **GhProxy 镜像加速链接**:
  ```text
  https://ghproxy.net/https://raw.githubusercontent.com/wen9529/hy2/main/clash.yaml
  ```
- **GitHub 官方原生 Raw 链接**:
  ```text
  https://raw.githubusercontent.com/wen9529/hy2/main/clash.yaml
  ```

### 2. Sing-box 订阅
```text
https://fastly.jsdelivr.net/gh/wen9529/hy2@main/singbox.json
```

### 3. 通用 Base64 订阅 (Shadowrocket 小火箭 / v2rayN)
```text
https://fastly.jsdelivr.net/gh/wen9529/hy2@main/sub.txt
```

---

## 📁 仓库核心文件说明

```text
├── workflows/
│   └── update-nodes.yml    # 工作流配置源文件 (复制到 .github/workflows/ 即可生效)
├── scripts/
│   └── convert.py          # 核心转换脚本 (主备镜像容灾、格式转换、YAML生成)
├── template.yaml           # Clash Meta 分流规则与策略组模板
├── urls.txt                # 待提取的节点 URL 列表 (支持主备镜像对)
├── requirements.txt        # Python 依赖清单
├── clash.yaml              # 自动生成的 Clash Meta 订阅文件 (工作流首次运行后生成)
├── singbox.json            # 自动生成的 Sing-box 配置文件
└── sub.txt                 # 自动生成的 Base64 订阅文本
```
