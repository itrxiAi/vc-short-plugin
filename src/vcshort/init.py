#!/usr/bin/env python3
"""视频项目工作空间初始化。

用法：vcshort init <项目名>
在当前目录下创建一个完整的视频制作工作空间。
"""

import sys
from pathlib import Path


# 目录结构定义：(相对路径, 是否为目录)
STRUCTURE = [
    ("", True),                         # 项目根目录
    ("script.md", False),               # 完整剧本
    ("config.yaml", False),             # 项目配置
    ("README.md", False),               # 使用说明
    ("assets", True),                   # 素材
    ("assets/characters", True),        # 角色
    ("assets/characters/.gitkeep", False),
    ("assets/scenes", True),            # 场景
    ("assets/scenes/.gitkeep", False),
    ("assets/costumes", True),          # 服装
    ("assets/costumes/.gitkeep", False),
    ("assets/props", True),             # 道具
    ("assets/props/.gitkeep", False),
    ("chapters", True),                 # 章节
    ("chapters/.gitkeep", False),
    ("output", True),                   # 最终合成
    ("output/.gitkeep", False),
]

# 模板文件内容
SCRIPT_TEMPLATE = """# {name}

<!-- 在这里写你的剧本 -->
<!-- 支持多章节，用 ## 标记章节标题 -->

## 第1章 末日黎明

【场景1：破败公寓客厅，清晨】

林浩（紧张地拉上窗帘）：妈，别看了，外面那些东西越来越多了。

林母（攥着他的手，声音发抖）：你爸出去找食物三天了，他还能回来吗？

林浩（沉默片刻，坚定）：会的。我们先准备好，天黑前必须离开这里。
"""

CONFIG_TEMPLATE = """# {name} 项目配置

# 视频风格
style: 动漫3D
aspect_ratio: "9:16"            # 竖屏短视频（含冒号需引号）

# API 配置
api:
  base_url: https://ark.cn-beijing.volces.com/api/v3
  api_key: ""                       # 填入火山引擎 ARK API Key
  image_model: doubao-seedream-4-5-251128  # 图片生成模型
  video_model: doubao-seedance      # 视频生成模型

# 角色和场景资产由 assets 目录结构决定，无需在此配置：
#   assets/characters/<角色名>/<角色名>.png          # 默认形态
#   assets/characters/<角色名>/<角色名>-<形态>.png    # 其他形态
#   assets/scenes/<场景名>/1.png, 2.png, ...         # 场景多图
"""

README_TEMPLATE = """# {name}

AI 短视频制作工作空间。

## 目录结构

```
{name}/
├── script.md              # 完整剧本
├── config.yaml            # 项目配置（风格、API）
├── assets/                # 素材
│   ├── characters/        # 角色定妆照（每个角色一个文件夹）
│   │   └── 林浩/          # 角色名
│   │       ├── 林浩.png       # 默认形态
│   │       └── 林浩-受伤.png  # 其他形态
│   ├── scenes/            # 场景图（每个场景一个文件夹，多张图片）
│   │   └── apartment/     # 场景名
│   │       ├── 1.png          # 数字命名，全部传入图生视频
│   │       └── 2.png
│   ├── costumes/          # 服装图
│   └── props/             # 道具图
├── chapters/              # 章节
│   └── ch01/              # 第1章
│       ├── novel.md       # 小说原文
│       ├── character_map.yaml  # 角色映射（小说名 → assets 目录名）
│       ├── scene_map.yaml      # 场景映射
│       └── shots/         # 分镜
│           ├── shot_001/
│           │   ├── shot.yaml      # 镜头参数
│           │   └── shot.mp4        # 生成视频
│           └── ...
├── output/                # 最终合成
```

## 使用方式

1. 在 `script.md` 写剧本
2. 跟 Devin 说：`/extract` 提取角色场景并生成图片
3. 跟 Devin 说：`/gen-shots` 拆分分镜
4. 跟 Devin 说：`/gen-video` 生成视频
"""


def create_project(name: str) -> None:
    """创建视频项目工作空间。"""
    root = Path(name)

    if root.exists():
        print(f"错误：目录 {name} 已存在")
        sys.exit(1)

    # 创建目录结构
    for rel_path, is_dir in STRUCTURE:
        full = root / rel_path
        if is_dir:
            full.mkdir(parents=True, exist_ok=True)
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.touch()

    # 写入模板文件
    (root / "script.md").write_text(
        SCRIPT_TEMPLATE.format(name=name), encoding="utf-8"
    )
    (root / "config.yaml").write_text(
        CONFIG_TEMPLATE.format(name=name), encoding="utf-8"
    )
    (root / "README.md").write_text(
        README_TEMPLATE.format(name=name), encoding="utf-8"
    )
    print(f"✅ 项目 {name} 已创建")
    print(f"   cd {name}")
    print(f"   编辑 script.md 写剧本，然后 /video 开始制作")


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1:
        print("用法：vcshort init <项目名>")
        return 1
    create_project(args[0])
    return 0
