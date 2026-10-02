---
name: gen-keyframe
description: 按分镜 keyframe_prompt 生成首帧图，不生成视频
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

# 生成首帧图

## 前置条件

- `vcshort` CLI 固定安装在 `~/.vc-short/`（Windows 为 `%USERPROFILE%\.vc-short`），自带 Python 运行时，无需系统安装 Python：
  - bash / Git Bash / macOS / Linux：`~/.vc-short/bin/vcshort <command> ...`
  - Windows cmd / PowerShell：`%USERPROFILE%\.vc-short\bin\vcshort.bat <command> ...`
- 下文 `vcshort <command>` 均指上述完整路径
- 若该路径不存在：代用户安装运行时——下载 `https://github.com/itrxiAi/vc-short-plugin/releases/latest/download/vcshort-macos.zip`（Windows 用 `vcshort-windows.zip`），解压并把其中的 `vc-short-plugin` 文件夹移动为 `~/.vc-short`（Windows 为 `%USERPROFILE%\.vc-short`），装好后重试

## 前置条件

- 项目已初始化（有 `config.yaml` 和 `chapters/` 目录）
- 分镜 YAML 已生成（`/vc-short:gen-shots` 已执行），shot YAML 含 `keyframe_prompt` 字段
- 分镜中引用的角色和场景图片已存在于 `assets/` 目录（作为参考图保身份和地理）
- 角色支持多形态：`assets/characters/<角色名>/` 下默认形态 `<角色名>.png`，其他形态 `<角色名>-<形态>.png`，shot 中用 `角色名`（取默认）或 `角色名:形态名` 引用

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
vcshort gen-keyframe <项目路径> \
  --chapter <章节号> \
  --shot <分镜号> \
  [--anchor <锚点规格>] \
  [--force]
```

- 已有 `keyframe.png` 时直接返回，不重复生成（避免额外花费）
- `--force`：覆盖已有 `keyframe.png`，重新生成
- `--anchor`：**当 shot 标了 `首帧来源：参考前帧` 时由你选锚点**——先 ls 前面分镜目录看有哪些帧图（`keyframe.png` 生成的首帧 / `first_frame.png` 视频实抽第一帧 / `last_frame.png` 视频尾帧），比较哪张与本镜起点衔接最好，再传参。写法：
  - `--anchor 尾帧` / `首帧` / `第一帧`：沿用上一镜，只选帧型
  - `--anchor 上一镜首帧` / `上上镜尾帧` / `shot_001_02第一帧`：完整指定镜位+帧型
  - `--anchor none`：不用锚点（上一镜画面与本镜差异过大时）
  - 不传时默认 `上一镜尾帧`；锚定的上一镜若与本镜景别/机位相同，首帧会近似复制锚点帧，宜换帧型或 none

脚本会自动完成以下操作：
1. 读取 `chapters/<章节号>/shots/shot_<分镜号>/shot.yaml`（含 `keyframe_prompt`、`characters`、`scene`）
2. 检查 `keyframe.png` 是否已存在：存在且未加 `--force` 直接返回；加 `--force` 先删除旧图
3. 校验 `keyframe_prompt` 是否存在，缺失则报错退出
4. 收集参考图：本镜角色图（保身份）+ 首张场景图（保地理）+ 本镜道具图（保外观），从 `assets/` 目录扫描（约定优于配置）。例外：shot.yaml 有 `keyframe_source: 上一镜尾帧` 时，以 `shot_<上一镜>/last_frame.png` 为图1连续性锚点，另附本镜角色图+场景图+道具图，提示词按本镜景别/机位重新构图（切镜头）、画面状态与尾帧保持连续；上一镜尚无尾帧时回退文本提示词
5. 拼接提示词：`<keyframe_prompt>，视频首帧，画面定格瞬间`，附加 `style` 和 `aspect_ratio`
6. 调用图片 API（doubao-seedream）生成首帧图，存为 `chapters/<章节号>/shots/shot_<分镜号>/keyframe.png`
7. 生成失败不阻断视频流程，返回非零退出码

### 3. 确认结果

- 向用户展示首帧图路径
- 提示用户确认满意后，再用 `/vc-short:gen-video` 生成视频（会自动使用此首帧图作为起始画面参考）
- 如果失败，展示错误信息

## 抽坏处理

首帧图与描述明显不符（构图错乱、人物多/少、身份错乱、画风跑偏、手部畸形）时，**不要直接重复生成**——每次重新生成都产生费用，必须先向用户说明本次采用的策略并获确认。

**连续抽卡降级**：同一镜头连续 2 次生成结果不合格，第三次起必须降低画面复杂度（精细手部动作、多人同框、复杂姿态优先砍），不再微调提示词重抽。

可选策略（可组合）：

- **简化画面**：画面描述只保留核心主体和站位，删掉次要元素
- **减少人物**：把非必要人物移出画面描述（与角色字段同步），减少模型要协调的对象
- **减少动作**：首帧只保留静态站位/朝向，去掉复杂姿态和动作要求
- **不依赖其他参考图**：锚点帧干扰构图时换 `--anchor none` 纯文本生成；参考图本身引入干扰时也可减少传入

## 注意事项

- **本命令只生成图片，不提交视频任务**，与 `/vc-short:gen-video` 分两步走，避免一次确认同时产生图片+视频两笔费用
- 首帧图是分镜最可控的起点：`keyframe_prompt`（拆分镜时生成）描述本镜起点画面
- 角色和场景图片必须已生成（`/vc-short:gen-image` 或 `/vc-short:gen-character`），否则会跳过缺失的参考图，影响身份和地理一致性
- 图片分辨率通过 `--size 2K` 控制，比例从 `config.yaml` 的 `aspect_ratio` 读取
- 生成完首帧图后，`/vc-short:gen-video` 会自动检测到 `keyframe.png` 并作为起始画面参考图传入
- 首帧图不满意时加 `--force` 重新生成，或用 `/vc-short:fix-image` 局部修改
