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

## 定位 vcshort 可执行文件

本插件自带 CLI 工具 `vcshort`，位于插件根目录的 `bin/vcshort`。首次调用先定位：
```bash
devin skills show vc-short:compose-chapter
```
`Base directory` 向上两级即为插件根目录，可执行文件在 `<插件根>/bin/vcshort`。

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
<插件根>/bin/vcshort compose-chapter <项目路径> \
  --chapter <章节号>
```

自定义输出文件名：
```bash
<插件根>/bin/vcshort compose-chapter <项目路径> \
  --chapter <章节号> \
  --output "第1章.mp4"
```

脚本会自动完成以下操作：
1. 扫描 `chapters/<章节号>/shots/shot_*/shot.mp4`，按分镜号排序
2. 用 opencv 逐帧读取并写入新视频
3. 输出到 `chapters/<章节号>/chapter.mp4`

### 3. 确认结果

- 向用户展示合成视频路径
- 如果失败，展示错误信息

## 注意事项

- 需要安装 `opencv-python`（`pip install opencv-python`），与 gen-video 共用依赖
- 分镜视频按 `shot_001`、`shot_002`... 顺序拼接
- 输出文件默认放在章节目录下
