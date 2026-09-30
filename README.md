# 🚀 Xray (VLESS Reality) 自动提取与 Clash Meta / Karing 订阅生成器

本项目通过 **GitHub Actions** 自动化定时任务：
1. 从 4 个文档中提取全部 8 个 Xray (VLESS Reality) 节点配置源；
2. 批量并发下载最新配置，主线路与备用镜像双重保障；
3. 将节点配置按照 `template.yaml` 渲染并生成带有分流策略组的完整 **Clash Meta / Karing 订阅 (`config.yaml`)**；
4. 同时输出 `clash.yaml`、`xray_config.json` 与 `singbox.json`；
5. 定时自动提交回本仓库并通过 jsDelivr CDN 极速分发，国内免翻墙直接拉取。

---

## 🔗 Karing / Clash Meta 订阅链接 (安卓/iOS/电脑通用)

> **Karing 用户直接使用此链接添加订阅即可：**

### 1. jsDelivr CDN 高速链接 (国内首选 ⭐ 推荐)
```text
https://fastly.jsdelivr.net/gh/wen9529/hy22@main/config.yaml
```

### 2. GhProxy 镜像加速链接 (备用)
```text
https://ghproxy.net/https://raw.githubusercontent.com/wen9529/hy22/main/config.yaml
```

### 3. GitHub 官方原生 Raw 链接
```text
https://raw.githubusercontent.com/wen9529/hy22/main/config.yaml
```

---

## ⚡ 首次启用工作流 (10 秒快速开启)

GitHub 出于安全保护机制，不允许第三方应用直接向 `.github/workflows/` 目录推送文件。
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

保存后，点击仓库顶部的 **Actions** 标签 ➔ 选择 **自动提取节点并生成全套订阅** ➔ 点击 **Run workflow** 即可立即触发第一次自动更新！
