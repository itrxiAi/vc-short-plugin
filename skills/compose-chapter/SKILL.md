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

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

## 前置条件

- 章节下所有分镜视频已生成（`/vc-short:gen-video` 已执行）
- 已安装 `opencv-python`（`pip install opencv-python`）

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |
| **输出文件名** | 可选，默认 `chapter.mp4` | `第1章.mp4` |
| **--no-subtitle** | 可选，不烧录字幕 | |

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

不烧录字幕：
```bash
vcshort compose-chapter <项目路径> \
  --chapter <章节号> \
  --no-subtitle
```

脚本会自动完成以下操作：
1. 扫描 `chapters/<章节号>/shots/shot_*/shot.mp4`，按分镜号排序
2. 用 ffmpeg concat 拼接所有分镜视频
3. 读取每个分镜的 `shot.yaml` 中的 `dialogue`，按时间轴生成 SRT 字幕文件
4. 用 ffmpeg 将字幕烧录到合成视频中（白色字体 + 黑色描边，底部居中）
5. 输出到 `chapters/<章节号>/chapter.mp4`，字幕文件保存在 `chapters/<章节号>/chapter.srt`

### 3. 确认结果

- 向用户展示合成视频路径
- 如果失败，展示错误信息

## 注意事项

- 需要安装 `opencv-python`（`pip install opencv-python`），与 gen-video 共用依赖
- 分镜视频按 `shot_001`、`shot_002`... 顺序拼接
- 输出文件默认放在章节目录下
- 字幕从每个分镜的 `shot.yaml` 的 `dialogue` 字段读取，格式为 `说话人：台词`
- 无对白的分镜不会生成字幕条目
- 字幕样式：PingFang SC 字体，22px，白色字体 + 黑色描边，底部居中
- 加 `--no-subtitle` 可跳过字幕烧录，只拼接视频
