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

## 定位 vcshort 可执行文件

本插件自带 CLI 工具 `vcshort`（编译后的单文件可执行程序），位于插件根目录的 `bin/vcshort`。

**首次调用时先定位插件路径：**
```bash
devin skills show vc-short:init
```
输出中的 `Base directory` 形如 `/path/to/vc-short-plugin/skills/init`，**向上两级**即为插件根目录，可执行文件在 `<插件根>/bin/vcshort`。

后续所有命令用 `<插件根>/bin/vcshort <command> ...` 调用。

## 初始化项目

当用户执行 `/vc-short:init <项目名>` 时：
1. 运行 `<插件根>/bin/vcshort init <项目名>`
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
