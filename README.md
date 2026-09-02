# vc-short-plugin

AI 短视频制作插件（剧本 → 资产 → 分镜 → 视频 → 合成），兼容 Devin、Claude Code、Cursor。

## 安装

### macOS / Linux

```bash
cd vc-short-plugin
bash install.sh
```

### Windows

```powershell
cd vc-short-plugin
powershell -ExecutionPolicy Bypass -File install.ps1
```

安装脚本会：
1. 自动下载 `vcshort` 二进制（如未编译）
2. 将 `vcshort` 加入 PATH
3. 弹出菜单选择安装到 Devin / Claude Code / Cursor / 全部

### 本地编译（可选）

如果不想下载预编译版本，可以本地编译：

```bash
cd vc-short-plugin
pip install -r requirements.txt
./build.sh
```

产物：`bin/vcshort`（单文件可执行程序，自包含 Python 运行时和所有依赖）。

## 使用

安装后技能通过 slash command 调用：

- `/vc-short:init <项目名>` — 初始化项目
- `/vc-short:extract` — 提取角色/场景
- `/vc-short:gen-image` — 生成图片资产
- `/vc-short:fix-image` — 修改图片
- `/vc-short:gen-script` — 改编剧本
- `/vc-short:gen-shots` — 拆分分镜
- `/vc-short:gen-video` — 生成分镜视频
- `/vc-short:compose-chapter` — 合成章节视频
- `/vc-short:config-manager list` — 列出资产

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
