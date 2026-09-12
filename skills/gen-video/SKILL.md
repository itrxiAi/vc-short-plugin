---
name: gen-video
description: 从分镜生成视频，调用图生视频 API
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

# 生成视频

## 前置条件

运行 `install.sh`（macOS/Linux）或 `install.ps1`（Windows）安装后，`vcshort` 已在 PATH 中，直接调用 `vcshort <command> ...`。

## 前置条件

- 项目已初始化（有 `config.yaml` 和 `chapters/` 目录）
- 分镜 YAML 已生成（`/vc-short:gen-shots` 已执行）
- 分镜中引用的角色和场景图片已存在于 `assets/` 目录
- 角色支持多形态：`assets/characters/<角色名>/` 下默认形态 `<角色名>.png`，其他形态 `<角色名>-<形态>.png`，shot 中用 `角色名`（取 默认）或 `角色名:形态名` 引用
- 场景支持多张图片：`assets/scenes/<场景名>/` 下数字命名的图片，图生视频时自动扫描全部传入

## 输入参数

| 参数 | 说明 | 示例 |
|------|------|------|
| **项目路径** | 项目根目录的绝对路径 | `/Users/.../末日求生` |
| **章节号** | 章节编号 | `ch01` |
| **分镜号** | 分镜编号 | `001_01` |

## 执行步骤

### 1. 收集参数

- 确认项目路径、章节号、分镜号
- 分镜号格式为 `主号_子号`（如 `001_01`、`001_02`）或纯数字（如 `001`）

### 2. 调用脚本

```bash
vcshort gen-video <项目路径> \
  --chapter <章节号> \
  --shot <分镜号>
```

脚本会自动完成以下操作：
1. 读取 `chapters/<章节号>/shots/shot_<分镜号>/shot.yaml`
2. 查找上一分镜的 `last_frame.png`（保持分镜间连贯性）
   - 同主号：`001_02` 找 `001_01` 的 last_frame
   - 跨主号：`002_01` 找 `001_XX` 最后一个子号的 last_frame
3. 从 `assets/` 目录扫描角色和场景的图片（约定优于配置）
4. 将上一镜参考帧 + 角色图 + 场景图转 base64，作为 `reference_image` 传给视频生成 API
5. 用 `visual_prompt` + 对白内容 + 镜头运动作为文本提示词
6. 提交异步任务，轮询直到完成
7. 下载视频到 `chapters/<章节号>/shots/shot_<分镜号>/shot.mp4`
8. 用 opencv 提取视频第一帧和最后一帧，保存为 `first_frame.png` 和 `last_frame.png`

视频是否已生成通过检查分镜文件夹内是否有对应 mp4 文件判断。

### 3. 确认结果

- 向用户展示视频路径
- 如果失败，展示错误信息

## 注意事项

- 视频生成是异步任务，通常需要 1-5 分钟
- 角色和场景图片必须已生成（`/vc-short:gen-image`），否则会跳过缺失的参考图
- 已有视频的分镜（`shots/shot_<分镜号>/shot.mp4` 已存在）会跳过，不重复生成
- 视频分辨率默认 720p，比例从 `config.yaml` 的 `aspect_ratio` 读取
- duration 从 shot YAML 的 `camera.duration` 读取，支持 5/10/15 秒
- **分镜连贯性**：生成视频后自动提取第一帧和最后一帧，下一个分镜生成时会用上一镜的 `last_frame.png` 作为参考，保持画面衔接
- **连续分镜顺序约束**：同一主号的分镜（如 `001_01`、`001_02`）必须顺序生成，不能并行。因为后一镜需要前一镜的 `last_frame.png`。不同主号的分镜可以并行
- 需要安装 `opencv-python`（`pip install opencv-python`），否则跳过帧提取
