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

- 本插件自带 Python 运行时，无需系统安装 Python
- `vcshort` CLI 位于插件根目录 `bin/` 下（插件根目录 = 本 SKILL.md 上两级目录）：
  - WorkBuddy / CodeBuddy：`${CODEBUDDY_SKILL_DIR}/../../bin/vcshort`
  - Claude Code：`${CLAUDE_PLUGIN_ROOT}/bin/vcshort`
  - Devin / Cursor：从技能源路径取上两级目录，拼接 `bin/vcshort`
- 下文 `vcshort <command>` 均指展开后的完整路径；Windows 也可用 `bincshort.bat`

```bash
vcshort <command> ...
```

## 初始化项目

当用户执行 `/vc-short:init <项目名>` 时：
1. 运行 `vcshort init <项目名>`
2. 告知用户项目已创建
3. 提示用户把小说原文放到 `chapters/ch01/novel.md`，放好后执行 `/vc-short:extract`
4. **到此为止，不要自动进入下一步，等待用户操作**

## 后续命令

init 只负责建目录。后续流程由用户通过对应命令触发，每个命令有自己的 SKILL.md：

- `/vc-short:extract` — 从小说原文提取角色/场景
- `/vc-short:gen-image` — 生成角色/场景图片
- `/vc-short:fix-image` — 修改已有图片
- `/vc-short:gen-script` — 改编剧本
- `/vc-short:gen-shots` — 拆分分镜
- `/vc-short:gen-video` — 生成分镜视频
- `/vc-short:compose-chapter` — 合成章节视频
- `/vc-short:config-manager list` — 列出已有资产
