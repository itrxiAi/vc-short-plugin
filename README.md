# vc-short-plugin

Devin 插件：AI 短视频制作全流程（剧本 → 资产 → 分镜 → 视频 → 合成）。

## 安装

### 1. 编译 CLI 可执行文件

```bash
cd vc-short-plugin
pip install -r requirements.txt
./build.sh
```

产物：`bin/vcshort`（单文件可执行程序，自包含 Python 运行时和所有依赖）。

### 2. 安装 Devin 插件

```bash
devin plugins install ./vc-short-plugin
```

本地安装是链接式，编辑 SKILL.md 后下次 session 即生效。

## 使用

安装后技能变成命名空间调用：

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
│   └── plugin.json          # 插件清单
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
├── requirements.txt         # Python 依赖
└── README.md
```

## 工作原理

每个 SKILL.md 里引用的脚本命令都改成 `vcshort <command>` 形式。Agent 首次调用时通过 `devin skills show vc-short:<skill>` 获取插件路径，推算出 `bin/vcshort` 的绝对位置后执行。

`vcshort` 是用 PyInstaller 编译的单文件可执行程序，自包含 Python 运行时和所有依赖（requests、ruamel.yaml、opencv、imageio-ffmpeg），用户机器不需要装 Python 环境。

## 依赖

- 火山引擎方舟 API Key（填入项目的 `config.yaml`）
- `opencv-python`、`imageio-ffmpeg`（已打包进可执行文件，无需单独安装）
