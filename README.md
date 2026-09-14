# vc-short-plugin

AI 短视频制作插件（剧本 → 资产 → 分镜 → 视频 → 合成），支持 WorkBuddy、Devin、Claude Code、Cursor。

## 安装

插件自带便携 Python 运行时（含全部依赖），**无需安装 Python、无需配置 PATH、无 PowerShell 依赖**。

### WorkBuddy（推荐，全程零命令行）

1. 从 [Releases](https://github.com/itrxiAi/vc-short-plugin/releases) 下载对应平台的 zip：
   - `vcshort-macos.zip`（Apple Silicon）
   - `vcshort-windows.zip`（Windows 64 位）
2. 解压到任意位置
3. 打开 WorkBuddy → 技能 → 添加技能 → 上传技能包，选择解压出的 `vc-short-plugin` 目录
4. 对话中直接使用

### Devin / Claude Code / Cursor

1. 下载并解压对应平台的 zip（同上）
2. 注册到 agent（任选其一）：

```bash
# Devin CLI
devin plugins install --local <解压目录>

# Claude Code（macOS/Linux）
ln -s <解压目录> ~/.claude/plugins/vc-short

# Claude Code（Windows，cmd 管理员外也可用 junction）
mklink /J "%USERPROFILE%\.claude\plugins\vc-short" "<解压目录>"

# Cursor：将解压目录拷贝或链接到 ~/.cursor/plugins/local/vc-short
```

安装完成后在 agent 对话中调用 `/vc-short:init` 等技能即可。

### 目录内容

```
vc-short-plugin/
├── skills/          # 11 个技能（SKILL.md）
├── bin/vcshort      # 启动器（bash）+ vcshort.bat（Windows cmd）
├── python/          # 便携 Python + site-packages（含 opencv、ffmpeg）
├── src/vcshort/     # CLI 源码
└── plugin.json      # 插件清单（WorkBuddy / Claude Code / Devin 兼容）
```

### 本地构建（可选）

```bash
git clone https://github.com/itrxiAi/vc-short-plugin.git
cd vc-short-plugin
./build.sh          # 组装 mac 包到 dist/vc-short-plugin/（CI 用同样逻辑构建三平台）
```

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
- `chapters/<章节号>/shots/shot_001_01/shot.yaml` — 分镜参数（`script_segment`、`characters`、`scene`、`camera`、`status: pending`）
- `chapters/<章节号>/shots/shot_001_02/shot.yaml` — 同主号 = 「同一地点 + 同一批角色」的连续分镜，子号递增
- `chapters/<章节号>/shots/shot_002_01/shot.yaml` — 地点或角色组变化后开新主号

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
│   └── plugin.json          # Claude Code / WorkBuddy 插件清单
├── plugin.json              # Cursor / Agent Plugins 清单
├── skills/                  # 11 个技能
│   ├── init/SKILL.md
│   ├── extract/SKILL.md
│   ├── gen-character/SKILL.md
│   ├── gen-image/SKILL.md
│   ├── fix-image/SKILL.md
│   ├── gen-voice/SKILL.md
│   ├── gen-script/SKILL.md
│   ├── gen-shots/SKILL.md
│   ├── gen-video/SKILL.md
│   ├── compose-chapter/SKILL.md
│   └── config-manager/SKILL.md
├── agents/                  # 子代理定义
├── src/vcshort/             # Python CLI 源码
│   ├── cli.py               # 主入口（subparsers 分发）
│   ├── init.py
│   ├── extract.py
│   ├── gen_image.py
│   ├── fix_image.py
│   ├── gen_voice.py
│   ├── gen_shots.py
│   ├── gen_video.py
│   ├── compose_chapter.py
│   └── config_manager.py
├── bin/vcshort              # 便携启动器（bash，macOS/Linux/Git Bash 通用）
├── bin/vcshort.bat          # 便携启动器（Windows cmd）
├── build.sh                 # 本地组装脚本（CI 同逻辑）
├── requirements.txt         # Python 依赖（装入便携 Python）
└── README.md
```

## 工作原理

- 插件自带便携 Python 运行时（[python-build-standalone](https://github.com/astral-sh/python-build-standalone) 官方构建），依赖在打包时装入 `python/`，用户机器**不需要装 Python 和任何依赖**
- SKILL.md 通过 `${CODEBUDDY_SKILL_DIR}` / `${CLAUDE_PLUGIN_ROOT}` / 技能源路径定位插件根目录下的 `bin/vcshort`，无需 PATH 配置
- `bin/vcshort`（bash）和 `bin/vcshort.bat`（cmd）启动器调用自带 Python 运行 `src/vcshort/__main__.py`
- CI（GitHub Actions）按 tag 触发，在 macOS / Windows runner 上组装便携包并发布 zip，无编译步骤、无杀软误报风险

## 依赖

- 火山引擎方舟 API Key（填入项目的 `config.yaml`）
- `opencv-python`、`imageio-ffmpeg`（已装入插件自带的便携 Python，无需单独安装）
