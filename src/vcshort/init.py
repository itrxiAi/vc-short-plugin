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
    ("chapters/ch01", True),            # 第1章
    ("chapters/ch01/novel.md", False),  # 小说原文（用户填写）
    ("output", True),                   # 最终合成
    ("output/.gitkeep", False),
]

# 模板文件内容
NOVEL_TEMPLATE = """<!-- 在这里粘贴小说原文 -->
<!-- 放好后执行 /vc-short:extract 开始制作 -->
"""


CONFIG_TEMPLATE = """# {name} 项目配置

# 视频风格
style: 动漫3D
aspect_ratio: "9:16"            # 竖屏短视频（含冒号需引号）

# API 配置
api:
  base_url: https://ark.cn-beijing.volces.com/api/v3
  api_key: ""                       # 填入火山引擎 ARK API Key
  image_model: doubao-seedream-5-0-260128  # 图片生成模型
  video_model: doubao-seedance-2-0-mini-260615  # 视频生成模型

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
│       ├── novel.md       # 小说原文（用户上传）
│       ├── script.md      # 改编剧本（gen-script 生成）
│       ├── character_map.yaml  # 角色映射（extract 生成）
│       ├── scene_map.yaml      # 场景映射（extract 生成）
│       └── shots/         # 分镜
│           ├── shot_001/
│           │   ├── shot.yaml      # 镜头参数
│           │   └── shot.mp4        # 生成视频
│           └── ...
├── output/                # 最终合成
```

## 使用方式

1. 把小说原文放到 `chapters/ch01/novel.md`
2. 跟 Devin 说：`/vc-short:extract` 提取角色场景并生成图片
3. 跟 Devin 说：`/vc-short:gen-script` 改编剧本
4. 跟 Devin 说：`/vc-short:gen-shots` 拆分分镜
5. 跟 Devin 说：`/vc-short:gen-video` 生成视频
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
    (root / "config.yaml").write_text(
        CONFIG_TEMPLATE.format(name=name), encoding="utf-8"
    )
    (root / "README.md").write_text(
        README_TEMPLATE.format(name=name), encoding="utf-8"
    )
    (root / "chapters/ch01/novel.md").write_text(
        NOVEL_TEMPLATE, encoding="utf-8"
    )
    print(f"✅ 项目 {name} 已创建")
    print(f"   cd {name}")
    print(f"   把小说原文放到 chapters/ch01/novel.md，然后 /vc-short:extract 开始制作")


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 1:
        print("用法：vcshort init <项目名>")
        return 1
    create_project(args[0])
    return 0
