---
name: gen-shots
description: 把 shots.md 编译成 shot YAML。用户在 shot-split、shot-design、shot-continuity 完成后说"编译分镜/生成 shot yaml/准备生成视频"时使用；不生成媒体，不改 shots.md。
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# 编译分镜

把 `chapters/<章节号>/shots.md` 编译成 `chapters/<章节号>/shots/shot_XXX_YY/shot.yaml`，供 gen-keyframe / gen-video 消费。

本步只做编译，不写分镜内容。分镜创作链路：shot-split → shot-design → shot-continuity → 本步。

## Quick Start

`vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时：
- bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
- Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`

下文 `vcshort <command>` 均指上述完整路径。若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`，装好后重试。

## 入口

- `chapters/<章节号>/shots.md` 已存在且经 shot-continuity 填完连续性字段（场景、角色@位置、道具、首帧提示词）。
- `shots/` 目录已有分镜时追加 `--force` 覆盖重编译。

## 工作流

```bash
vcshort gen-shots <项目路径> --chapter <章节号> [--force]
```

1. 跑 CLI。解析 `## SHOT-场序-镜序` 块，逐镜生成 `shot.yaml`。
2. 报错按行号回 shots.md 修字段，修好重跑——不要在 CLI 之外手改 shot.yaml。
3. 成功后列出分镜总数和 `shots/` 目录请用户确认。

## 编译出的 YAML

- `script_segment`（声音）、`action`（动作）、`performance`（表演）、`keyframe_prompt`（首帧提示词）原样落盘
- `characters`/`scene`/`props` 按 `character_map.yaml`、`scene_map.yaml`、`prop_map.yaml` 映射为 assets 目录名；映射不到保留原名，可改映射文件后重编译
- `video_prompt` 预生成——与 gen-video 调 API 提交的 prompt_text 一致，含 @图片N/@音频N 引用；`video_ref_images`/`video_ref_audios` 是对应上传顺序

## 修订

shots.md 改动后重跑 `vcshort gen-shots --force` 重编译全部镜头。已生成首帧图/视频的镜头，其 `keyframe.png`、`shot.mp4`、`first_frame.png`、`last_frame.png` 保留在分镜目录里，重编译不删。

## 完成

`shots/shot_<场序>_<镜序>/shot.yaml` 全部生成且无报错，即完成。下一步由用户点名 `/vc-short:gen-keyframe` 或 `/vc-short:gen-video`。
