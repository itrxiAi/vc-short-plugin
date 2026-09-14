---
name: compose-chapter
description: 合成章节视频，将一个章节下所有分镜视频拼接成一个完整视频
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

# 合成章节视频

## 前置条件

- 本插件自带 Python 运行时，无需系统安装 Python
- `vcshort` CLI 位于插件根目录 `bin/` 下（插件根目录 = 本 SKILL.md 上两级目录）：
  - WorkBuddy / CodeBuddy：`${CODEBUDDY_SKILL_DIR}/../../bin/vcshort`
  - Claude Code：`${CLAUDE_PLUGIN_ROOT}/bin/vcshort`
  - Devin / Cursor：从技能源路径取上两级目录，拼接 `bin/vcshort`
- 下文 `vcshort <command>` 均指展开后的完整路径；Windows 也可用 `bincshort.bat`

## 前置条件

- 章节下所有分镜视频已生成（`/vc-short:gen-video` 已执行）
- 已安装 `opencv-python`（`pip install opencv-python`）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |
| **输出文件名** | 可选，默认 `chapter.mp4` | `第1章.mp4` |

## 执行步骤

### 1. 收集参数

- 确认项目路径、章节号

### 2. 调用脚本

```bash
vcshort compose-chapter <项目路径> \
  --chapter <章节号>
```

自定义输出文件名：
```bash
vcshort compose-chapter <项目路径> \
  --chapter <章节号> \
  --output "第1章.mp4"
```

脚本会自动完成以下操作：
1. 扫描 `chapters/<章节号>/shots/shot_*/shot.mp4`，按分镜号排序
2. 用 ffmpeg concat 拼接所有分镜视频
3. 输出到 `chapters/<章节号>/chapter.mp4`

### 3. 确认结果

- 向用户展示合成视频路径
- 如果失败，展示错误信息

## 注意事项

- 需要安装 `opencv-python`（`pip install opencv-python`），与 gen-video 共用依赖
- 分镜视频按 `shot_001`、`shot_002`... 顺序拼接
- 输出文件默认放在章节目录下
