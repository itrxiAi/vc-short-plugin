# vc-short-plugin

AI 短视频制作插件（剧本 → 资产 → 分镜 → 视频 → 合成），兼容 Devin、Claude Code、Cursor。

## 安装

### macOS / Linux

一行命令安装：

```bash
curl -fsSL https://raw.githubusercontent.com/itrxiAi/vc-short-plugin/main/install.sh | bash
```

### Windows

一行命令安装（PowerShell 7+）：

```powershell
irm https://raw.githubusercontent.com/itrxiAi/vc-short-plugin/main/install.ps1 | iex
```

Windows PowerShell 5.1（Windows 10 默认）对中文编码支持较差，建议安装 PowerShell 7：

```powershell
winget install Microsoft.PowerShell
```

然后用 `pwsh` 代替 `powershell` 运行上述命令。

安装脚本会自动完成：
1. 创建安装目录（`~/.vcshort/` 或 `%USERPROFILE%\.vcshort\`）
2. 下载插件文件（skills、plugin.json 等，不需要 git）
3. 下载对应平台的 `vcshort` 二进制
4. 将 `vcshort` 加入 PATH
5. 弹出菜单选择安装到 Devin / Claude Code / Cursor / 全部

安装完成后重新打开终端，运行 `vcshort --help` 验证。

### 本地编译（可选）

如果不想下载预编译版本，可以本地编译：

```bash
git clone https://github.com/itrxiAi/vc-short-plugin.git
cd vc-short-plugin
pip install -r requirements.txt
./build.sh
```

产物：`bin/vcshort`（单文件可执行程序，自包含 Python 运行时和所有依赖）。

## 使用

安装后技能通过 slash command 调用，建议按顺序执行：

### `/vc-short:init <项目名>` — 初始化项目

创建项目骨架目录。**产物：**

- `<项目名>/config.yaml` — 全局配置（`style`、`aspect_ratio`、`api.api_key`）
- `<项目名>/assets/` — 资产根目录（含 `characters/`、`scenes/`、`costumes/`、`props/` 子目录）
- `<项目名>/chapters/` — 章节根目录

执行后需手动把小说原文放到 `chapters/ch01/novel.md`，再进入下一步。

### `/vc-short:extract` — 提取角色/场景

从 `chapters/<章节号>/novel.md` 提取角色和场景，与已有 `assets/` 目录匹配，用户确认后生成映射。**产物：**

- `chapters/<章节号>/extract.tmp.json` — 临时文件（LLM 生成 → 脚本写回 `matched` → 用户确认 → `--confirm` 后删除）
- `chapters/<章节号>/character_map.yaml` — 角色映射（剧本角色名 → assets 目录名，最终版）
- `chapters/<章节号>/scene_map.yaml` — 场景映射（剧本场景描述 → assets 目录名）

未匹配的新资产需用 `/vc-short:gen-image` 生成图片。

### `/vc-short:gen-image` — 生成图片资产

调用 doubao-seedream API 生成角色/服装/道具/场景图片，保存到 `assets/` 目录。**产物：**

- 角色：`assets/characters/<角色名>/<角色名>.png`（默认形态）或 `<角色名>-<形态>.png`（其他形态）
- 服装：`assets/costumes/<服装名>.png`
- 道具：`assets/props/<道具名>.png`
- 场景：`assets/scenes/<场景名>/<N>.png`（数字递增，支持多张）

### `/vc-short:fix-image` — 修改图片

基于原图 + 提示词调用 doubao-seededit API 编辑已有资产。**产物：**

- 覆盖原图片文件（如 `assets/characters/<角色名>/<角色名>.png`）
- `<原文件名>.png.bak` — 原图自动备份，不满意可恢复

### `/vc-short:gen-script` — 改编剧本

将 `chapters/<章节号>/novel.md` 改编为适合 1-3 分钟短视频的剧本。**产物：**

- `chapters/<章节号>/script.md` — 改编剧本（用 `【场景X：描述，时间】` 分隔，精简对白、动作可视化）

### `/vc-short:gen-shots` — 拆分分镜

读取剧本和映射文件，拆分为多个 10 秒分镜，写入 YAML。**产物：**

- `chapters/<章节号>/shots.json` — 临时 JSON（脚本消费后删除）
- `chapters/<章节号>/shots/shot_001/shot.yaml` — 分镜参数（`visual_prompt`、`characters`、`scene`、`camera`、`dialogue`、`status: pending`）
- `chapters/<章节号>/shots/shot_002/shot.yaml` … 依次递增

### `/vc-short:gen-video` — 生成分镜视频

调用图生视频 API，将分镜 YAML 转为视频，并提取首尾帧保持分镜连贯。**产物：**

- `chapters/<章节号>/shots/shot_<N>/shot.mp4` — 分镜视频（5 或 10 秒，分辨率 720p）
- `chapters/<章节号>/shots/shot_<N>/first_frame.png` — 视频首帧
- `chapters/<章节号>/shots/shot_<N>/last_frame.png` — 视频尾帧（下一分镜生成时作为参考图）

### `/vc-short:compose-chapter` — 合成章节视频

用 ffmpeg concat 按分镜号顺序拼接章节下所有 `shot.mp4`。**产物：**

- `chapters/<章节号>/chapter.mp4` — 章节完整视频（可用 `--output` 自定义文件名）

### `/vc-short:config-manager list` — 列出资产

扫描 `assets/` 目录，按角色/场景/服装/道具分类列出已有资产及图片数量，不产生文件，仅打印到终端。

## 目录结构

```
vc-short-plugin/
├── .devin-plugin/
│   └── plugin.json          # Devin 插件清单
├── .claude-plugin/
│   └── plugin.json          # Claude Code 插件清单
├── plugin.json              # Cursor / Agent Plugins 清单
├── skills/                  # 9 个技能
│   ├── init/SKILL.md
│   ├── extract/SKILL.md
│   ├── gen-image/SKILL.md
│   ├── fix-image/SKILL.md
│   ├── gen-script/SKILL.md
│   ├── gen-shots/SKILL.md
│   ├── gen-video/SKILL.md
│   ├── compose-chapter/SKILL.md
│   └── config-manager/SKILL.md
├── src/vcshort/             # Python CLI 源码
│   ├── cli.py               # 主入口（subparsers 分发）
│   ├── init.py
│   ├── extract.py
│   ├── gen_image.py
│   ├── fix_image.py
│   ├── gen_shots.py
│   ├── gen_video.py
│   ├── compose_chapter.py
│   └── config_manager.py
├── bin/vcshort              # 编译后的可执行文件（build.sh 生成）
├── vcshort.spec             # PyInstaller 打包配置
├── build.sh                 # 一键打包脚本
├── install.sh               # 安装脚本（macOS/Linux）
├── install.ps1              # 安装脚本（Windows）
├── requirements.txt         # Python 依赖
└── README.md
```

## 工作原理

安装脚本将 `vcshort` 加入 PATH，SKILL.md 中直接调用 `vcshort <command>`，无需定位插件路径。

`vcshort` 是用 PyInstaller 编译的单文件可执行程序，自包含 Python 运行时和所有依赖（requests、ruamel.yaml、opencv、imageio-ffmpeg），用户机器不需要装 Python 环境。

## 依赖

- 火山引擎方舟 API Key（填入项目的 `config.yaml`）
- `opencv-python`、`imageio-ffmpeg`（已打包进可执行文件，无需单独安装）
