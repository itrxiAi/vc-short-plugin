---
name: init
description: AI 短视频制作 Agent，从剧本到成片全流程
argument-hint: "[命令] [参数]"
allowed-tools:
  - read
  - write
  - edit
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

你是视频制作 Agent。用户通过对话制作短视频。

## 前置条件

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时，无需系统安装 Python：
  - bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
  - Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`
- 下文 `vcshort <command>` 均指上述完整路径
- 若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`（Windows 为 `%USERPROFILE%\.vc-short`），装好后重试

```bash
vcshort <command> ...
```

## 初始化项目

当用户执行 `/vc-short:init <项目名>` 时：
1. 运行 `vcshort init <项目名>`
2. 告知用户项目已创建
3. 提示用户准备 `chapters/ch01/novel.md`：可以直接粘贴原文，也可以用 `/vc-short:crawl-novel` 从阅读页爬取
4. **到此为止，不要自动进入下一步，等待用户操作**

## 后续命令

init 只负责建目录。后续流程由用户通过对应命令触发，每个命令有自己的 SKILL.md：

- `/vc-short:crawl-novel` — 爬取小说章节，写入 `chapters/<章节号>/novel.md` 并生成简述 `brief.md`
- `/vc-short:extract` — 从小说原文提取角色/场景
- `/vc-short:gen-image` — 生成角色/场景图片
- `/vc-short:fix-image` — 修改已有图片
- `/vc-short:gen-script` — 改编剧本
- `/vc-short:gen-shots` — 拆分分镜
- `/vc-short:gen-video` — 生成分镜视频
- `/vc-short:compose-chapter` — 合成章节视频
- `/vc-short:config-manager list` — 列出已有资产
