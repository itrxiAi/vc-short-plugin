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

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时，无需系统安装 Python：
  - bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
  - Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`
- 下文 `vcshort <command>` 均指上述完整路径
- 若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`（Windows 为 `%USERPROFILE%\.vc-short`），装好后重试

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

从指定分镜目录合成（如 `shots001`）：
```bash
vcshort compose-chapter <项目路径> \
  --chapter <章节号> \
  --shots-dir shots001
```

脚本会自动完成以下操作：
1. 扫描 `chapters/<章节号>/<shots-dir>/shot_*/shot.mp4`，按分镜号排序
2. 用 ffmpeg concat 拼接所有分镜视频
3. 输出到 `chapters/<章节号>/chapter.mp4`

### 3. 确认结果

- 向用户展示合成视频路径
- 如果失败，展示错误信息

## 注意事项

- 需要安装 `opencv-python`（`pip install opencv-python`），与 gen-video 共用依赖
- 分镜视频按 `shot_001`、`shot_002`... 顺序拼接
- 输出文件默认放在章节目录下
