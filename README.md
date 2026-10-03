# vc-short-plugin

AI 短视频制作插件（剧本 → 资产 → 分镜 → 视频 → 合成），支持 WorkBuddy、Devin、Claude Code、Cursor。

## 安装

分两部分：**CLI**（`vcshort` 命令，通过 pip 安装）和**插件**（`skills/` 目录，通过各 agent 的插件机制安装）。skill 里直接调用 `vcshort`，不依赖固定路径。

### 1. 安装 Python

- **Windows**：https://www.python.org/downloads/windows/ 下载 `python-3.x.x-amd64.exe`，安装时勾选 **Add Python to PATH**
- **macOS**：`brew install python@3.12` 或从 python.org 下载安装包
- **Linux**：`sudo apt install python3 python3-pip`

### 2. 安装 vcshort CLI

发布到 PyPI 后：

```bash
pip install vcshort
```

本地源码安装：

```bash
git clone https://github.com/itrxiAi/vc-short-plugin.git
cd vc-short-plugin
pip install -e .
```

### 3. 安装 agent 插件

插件目录需要让 agent 能读到 `skills/` 下的 `SKILL.md`。

### WorkBuddy

WorkBuddy → 插件市场 → 添加市场 → 填入本仓库地址
`https://github.com/itrxiAi/vc-short-plugin` → 搜索 `vc-short` → 安装
（或 CLI 内：`/plugin marketplace add itrxiAi/vc-short-plugin` → `/plugin install vc-short@vc-short`）

### Devin / Claude Code / Cursor

指向仓库克隆目录（假设 clone 到 `~/vc-short-plugin`）：

```bash
# Devin CLI
devin plugins install --local ~/vc-short-plugin

# Claude Code（macOS/Linux）
ln -s ~/vc-short-plugin ~/.claude/plugins/vc-short

# Claude Code（Windows，cmd）
mklink /J "%USERPROFILE%\.claude\plugins\vc-short" "%USERPROFILE%\vc-short-plugin"

# Cursor：将 ~/vc-short-plugin 拷贝或链接到 ~/.cursor/plugins/local/vc-short
```

安装完成后在 agent 对话中调用 `/vc-short:init` 等技能即可。

### 目录内容

```
vc-short-plugin/
├── skills/          # 12 个技能（SKILL.md）
├── agents/          # 子代理（script-reviewer）
├── src/vcshort/     # CLI 源码
├── pyproject.toml   # 包元数据与依赖
├── requirements.txt # 依赖列表
├── .codebuddy-plugin/marketplace.json   # WorkBuddy/CodeBuddy 插件市场清单
└── plugin.json      # 插件清单（WorkBuddy / Claude Code / Devin 兼容）
```

### 本地构建与发布（可选）

```bash
git clone https://github.com/itrxiAi/vc-short-plugin.git
cd vc-short-plugin
./build.sh          # 构建 wheel/sdist 并本地验证
```

发布到 PyPI：

```bash
python -m twine upload dist/*
```

或打 tag 触发 GitHub Actions 自动发布（见 `.github/workflows/publish.yml`）。

## 使用

安装后技能通过 slash command 调用，建议按顺序执行：

### `/vc-short:init <项目名>` — 初始化项目

创建项目骨架目录。**产物：**

- `<项目名>/config.yaml` — 全局配置（`style`、`aspect_ratio`、`api.api_key`）
- `<项目名>/assets/` — 资产根目录（含 `characters/`、`scenes/`、`costumes/`、`props/` 子目录）
- `<项目名>/chapters/` — 章节根目录

执行后需准备 `chapters/ch01/novel.md`：可以直接粘贴小说原文，也可以用 `/vc-short:crawl-novel` 从阅读页爬取。

### `/vc-short:crawl-novel` — 爬取小说章节

用 Playwright 打开小说阅读页，带重叠滚动截图，再由 Agent 逐张读图转写。**产物：**

- `chapters/<章节号>/novel.md` — 该章小说原文
- `chapters/<章节号>/brief.md` — 该章简述（一句话梗概、出场人物、场景、主要事件、章末钩子）
- 中间产物（截图、拼接预览图、crawl.json）放在 `<项目>/.crawl/ch<NN>/`，转写完成后删除；章节目录下保留 `novel.md` 和 `brief.md`

阅读页正文用自定义字体混淆，DOM 文本不可用，因此必须读截图转写，不读 DOM、不调用 OCR。不绕过登录、验证码或付费墙，检测到付费墙即停止并报告。

依赖**系统 `python3` + playwright**（插件便携 Python 不含）：`python3 -m pip install playwright && python3 -m playwright install chromium`。

### `/vc-short:extract` — 提取角色/场景/道具

从 `chapters/<章节号>/script.md` 提取角色、场景和道具，缺描述时按需 grep `novel.md` 搜名字补描述，与已有 `assets/` 目录匹配，用户确认后生成映射和 asset yaml。**产物：**

- `chapters/<章节号>/extract.tmp.json` — 临时文件（LLM 生成 → 脚本写回 `matched` → 用户确认 → `--confirm` 后删除）
- `chapters/<章节号>/character_map.yaml` — 角色映射（剧本角色名 → assets 目录名，最终版）
- `chapters/<章节号>/scene_map.yaml` — 场景映射（剧本场景描述 → assets 目录名）
- `chapters/<章节号>/prop_map.yaml` — 道具映射（剧本道具名 → assets 目录名）
- `assets/characters/<名称>/character.yaml` — 角色档案（不覆盖已有）
- `assets/scenes/<名称>/scene.yaml` — 场景档案（不覆盖已有）
- `assets/props/<名称>/prop.yaml` — 道具档案（不覆盖已有）

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

将 `chapters/<章节号>/novel.md` 改编为适合短视频的剧本。**产物：**

- `chapters/<章节号>/script.md` — 改编剧本（场景用 `## SC001 内 · 地点 · 时间` 标题分隔，按戏剧工作切场景，不按时长；支持 `[连续性]`/`[画面文字]`/`[转场]` 生产标签）

### `/vc-short:gen-shots` — 拆分分镜

按镜头职责拆分：每镜有唯一职责（本镜结束时观众知道了什么变化）、`起点 → 唯一动作 → 终点` 状态链、对白估时定档（5/10/15 秒）、冻结首帧提示词。LLM 直接写 Markdown 分镜文档，CLI 编译为 shot YAML。**产物：**

- `chapters/<章节号>/shots.md` — 分镜文档（drama 风格 `## SHOT-场序-镜序` 块，人可读的创作产物，保留不删）
- `chapters/<章节号>/shots/shot_001_01/shot.yaml` — 分镜参数（`source`、`purpose`、`script_segment`、`action`、`keyframe_prompt`、`end_state`、`characters`、`scene`、`camera`、`status: pending`）
- `chapters/<章节号>/shots/shot_001_02/shot.yaml` — 同主号 = 「同一地点 + 同一批角色」的连续分镜，子号递增
- `chapters/<章节号>/shots/shot_002_01/shot.yaml` — 地点或角色组变化后开新主号

### `/vc-short:gen-video` — 生成分镜视频

调用图生视频 API，将分镜 YAML 转为视频，并提取首尾帧保持分镜连贯。首帧优先用 `keyframe.png`（可用 `--with-keyframe` 按 `keyframe_prompt` 自动生成），无首帧图时用上一镜尾帧保持连贯。**产物：**

- `chapters/<章节号>/shots/shot_<N>/shot.mp4` — 分镜视频（5/10/15 秒，分辨率 720p）
- `chapters/<章节号>/shots/shot_<N>/keyframe.png` — 首帧图（可选，`--with-keyframe` 自动生成）
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
├── skills/                  # 12 个技能
│   ├── init/SKILL.md
│   ├── crawl-novel/SKILL.md
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
├── build.sh                 # 本地构建脚本：生成 wheel/sdist 并验证
├── pyproject.toml           # 包元数据、依赖与 console_scripts 入口
├── requirements.txt         # 依赖列表（与 pyproject.toml 同步）
└── README.md
```

## 工作原理

- 用户机器需自行安装 **Python 3.10+**
- `pip install vcshort` 后，`vcshort` 命令加入 PATH，skill 里直接调用
- `src/vcshort/__main__.py` 是 `python -m vcshort` 入口；`vcshort` 命令由 `pyproject.toml` 的 `[project.scripts]` 注册
- 技能目录（`skills/`）由各 agent 的插件机制加载；skill 与 CLI 通过 `vcshort` 命令解耦
- CI 按 tag 触发：
  - `.github/workflows/build.yml` 验证源码并打包 wheel
  - `.github/workflows/publish.yml` 把 wheel 上传到 PyPI

## 依赖

- 系统 Python 3.10+ 及 `pyproject.toml` 中的包：`requests`、`PyYAML`、`ruamel.yaml`、`opencv-python-headless`、`imageio-ffmpeg`
- 火山引擎方舟 API Key（填入项目的 `config.yaml`）
