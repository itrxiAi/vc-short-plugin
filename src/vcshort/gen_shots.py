#!/usr/bin/env python3
"""分镜拆分 — 将章节文本拆分为多个分镜 YAML 文件

用法：
  vcshort gen-shots <项目路径> --chapter <章节号> [--force]

LLM 分析章节文本后，将分镜数据以 JSON 形式写入 chapters/<章节号>/shots.json，
本脚本负责写入格式一致的 YAML 文件。

JSON 格式示例：
[
  {
    "script_segment": "林浩（紧张地拉上窗帘）：妈，别看了...",
    "visual_prompt": "破败公寓客厅，清晨，光线昏暗...",
    "characters": ["maxiaoshuai"],
    "scene": "apartment",
    "camera": {"shot_type": "中景", "angle": "平视", "movement": "固定", "duration": 5},
    "dialogue": [{"speaker": "maxiaoshuai", "text": "妈，别看了", "emotion": "紧张"}]
  },
  {
    "script_segment": "（无对白的环境描写）",
    "visual_prompt": "公寓外景，丧尸游荡",
    "characters": [],
    "scene": "street",
    "camera": {"shot_type": "全景", "angle": "俯视", "movement": "缓慢平移", "duration": 4},
    "dialogue": null
  }
]
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
except ImportError:
    print("错误：需要 ruamel.yaml，请运行 pip install ruamel.yaml", file=sys.stderr)
    sys.exit(1)


def load_character_map(project_root: Path, chapter: str) -> dict:
    """加载章节角色映射文件。"""
    map_path = project_root / "chapters" / chapter / "character_map.yaml"
    if not map_path.exists():
        return {}
    yaml = YAML()
    yaml.allow_unicode = True
    with open(map_path, encoding="utf-8") as f:
        return yaml.load(f) or {}


def load_scene_map(project_root: Path, chapter: str) -> dict:
    """加载章节场景映射文件。"""
    map_path = project_root / "chapters" / chapter / "scene_map.yaml"
    if not map_path.exists():
        return {}
    yaml = YAML()
    yaml.allow_unicode = True
    with open(map_path, encoding="utf-8") as f:
        return yaml.load(f) or {}


def map_characters(characters: list, char_map: dict) -> list:
    """将剧本角色名映射为 assets 目录名。"""
    result = []
    for char in characters:
        if char in char_map:
            result.append(char_map[char])
        else:
            result.append(char)
    return result


def map_dialogue(dialogue: list, char_map: dict) -> list:
    """将对白中的 speaker 映射为 assets 目录名。"""
    if not dialogue:
        return dialogue
    result = []
    for d in dialogue:
        d_copy = dict(d)
        speaker = d_copy.get("speaker", "")
        if speaker in char_map:
            d_copy["speaker"] = char_map[speaker]
        result.append(d_copy)
    return result


def map_scene(scene: str, scene_map: dict) -> str:
    """将剧本场景描述映射为 assets 目录名。"""
    if scene and scene in scene_map:
        return scene_map[scene]
    return scene


def write_shot_yaml(filepath: Path, shot_data: dict, shot_id: str, chapter: str, char_map: dict, scene_map: dict) -> None:
    """写入单个分镜 YAML 文件，用 ruamel.yaml 保证格式一致。"""
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096

    data = CommentedMap()

    data["shot_id"] = shot_id
    data["chapter"] = chapter
    data.yaml_set_comment_before_after_key("shot_id", before=f"分镜 {shot_id}")

    # 剧本片段
    data["script_segment"] = shot_data.get("script_segment", "").strip()
    data.yaml_set_comment_before_after_key("script_segment", before="剧本片段（原文）")

    # 画面描述
    data["visual_prompt"] = shot_data.get("visual_prompt", "")
    data.yaml_set_comment_before_after_key("visual_prompt", before="画面描述（用于关键帧生成）")

    # 角色引用
    characters = map_characters(shot_data.get("characters") or [], char_map)
    data["characters"] = characters if characters else []
    data.yaml_set_comment_before_after_key("characters", before="角色引用（对应 assets 目录名）")

    # 场景引用
    scene = map_scene(shot_data.get("scene"), scene_map)
    data["scene"] = scene if scene else None
    data.yaml_set_comment_before_after_key("scene", before="场景引用（对应 assets 目录名）")

    # 镜头参数
    camera = shot_data.get("camera") or {}
    cam_map = CommentedMap()
    cam_map["shot_type"] = camera.get("shot_type", "中景")
    cam_map["angle"] = camera.get("angle", "平视")
    cam_map["movement"] = camera.get("movement", "固定")
    cam_map["duration"] = camera.get("duration", 10)
    data["camera"] = cam_map
    data.yaml_set_comment_before_after_key("camera", before="镜头参数")

    # 对白
    dialogue = map_dialogue(shot_data.get("dialogue"), char_map)
    if dialogue:
        dia_list = []
        for d in dialogue:
            item = CommentedMap()
            item["speaker"] = d.get("speaker", "")
            item["text"] = d.get("text", "")
            item["emotion"] = d.get("emotion", "")
            dia_list.append(item)
        data["dialogue"] = dia_list
    else:
        data["dialogue"] = None
    data.yaml_set_comment_before_after_key("dialogue", before="对白/旁白（列表，可多段）")

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


def scan_existing_characters(project_root: Path) -> list:
    """扫描 assets/characters/ 目录，返回已有角色名列表。"""
    char_dir = project_root / "assets" / "characters"
    if not char_dir.is_dir():
        return []
    return [d.name for d in char_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def scan_existing_scenes(project_root: Path) -> list:
    """扫描 assets/scenes/ 目录，返回已有场景名列表。"""
    scene_dir = project_root / "assets" / "scenes"
    if not scene_dir.is_dir():
        return []
    return [d.name for d in scene_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def generate_map_files(project_root: Path, chapter: str, shots: list) -> tuple:
    """从 shots.json 和 assets 目录自动生成 character_map.yaml 和 scene_map.yaml。
    返回 (char_map, scene_map)。
    """
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096

    chapter_dir = project_root / "chapters" / chapter

    # 收集 shots.json 中出现的所有角色名和场景名
    char_names = set()
    scene_names = set()
    for shot in shots:
        for c in shot.get("characters") or []:
            char_names.add(c)
        for d in shot.get("dialogue") or []:
            if d.get("speaker"):
                char_names.add(d["speaker"])
        if shot.get("scene"):
            scene_names.add(shot["scene"])

    # 生成角色映射：尝试从 assets 目录匹配
    existing_chars = scan_existing_characters(project_root)
    char_map = CommentedMap()
    for name in sorted(char_names):
        # 精确匹配角色名
        if name in existing_chars:
            char_map[name] = name
        else:
            # 未匹配，留空让用户手动填
            char_map[name] = ""
    char_map_path = chapter_dir / "character_map.yaml"
    with open(char_map_path, "w", encoding="utf-8") as f:
        f.write("# 角色映射 — 剧本角色名 → assets 目录名\n")
        f.write("# 支持多形态：值可填 角色名:形态名（如 小帅:女装）\n")
        f.write("# 未填的请手动补充\n\n")
        yaml.dump(char_map, f)
    print(f"已生成角色映射: {char_map_path}")

    # 生成场景映射
    existing_scenes = scan_existing_scenes(project_root)
    scene_map = CommentedMap()
    for name in sorted(scene_names):
        if name in existing_scenes:
            scene_map[name] = name
        else:
            scene_map[name] = ""
    scene_map_path = chapter_dir / "scene_map.yaml"
    with open(scene_map_path, "w", encoding="utf-8") as f:
        f.write("# 场景映射 — 剧本场景描述 → assets 目录名\n")
        f.write("# 未填的请手动补充\n\n")
        yaml.dump(scene_map, f)
    print(f"已生成场景映射: {scene_map_path}")

    return dict(char_map), dict(scene_map)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort gen-shots", description="拆分分镜，生成 YAML 文件")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--force", action="store_true", help="覆盖已有分镜文件")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    chapter_dir = project_root / "chapters" / args.chapter
    shots_dir = chapter_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    # 自动读取 shots.json
    shots_json_path = chapter_dir / "shots.json"
    if not shots_json_path.exists():
        print(f"错误：找不到 {shots_json_path}，请先生成分镜数据 JSON 文件", file=sys.stderr)
        return 1

    # 加载 config.yaml（仅用于检查项目有效性）
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print(f"错误：config.yaml 不存在: {config_path}", file=sys.stderr)
        return 1

    try:
        with open(shots_json_path, encoding="utf-8") as f:
            shots = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误：JSON 解析失败: {e}", file=sys.stderr)
        return 1

    # 加载角色和场景映射（不存在则自动生成）
    char_map_path = chapter_dir / "character_map.yaml"
    scene_map_path = chapter_dir / "scene_map.yaml"
    if not char_map_path.exists() or not scene_map_path.exists():
        char_map, scene_map = generate_map_files(project_root, args.chapter, shots)
    else:
        char_map = load_character_map(project_root, args.chapter)
        scene_map = load_scene_map(project_root, args.chapter)
    if char_map:
        print(f"已加载角色映射: {char_map}")
    if scene_map:
        print(f"已加载场景映射: {scene_map}")

    if not isinstance(shots, list) or not shots:
        print("错误：shots-json 必须是非空数组", file=sys.stderr)
        return 1

    # 检查已有文件
    if not args.force:
        existing = list(shots_dir.glob("shot_*/shot_*.yaml"))
        if existing:
            print(f"错误：{shots_dir} 下已有分镜文件。使用 --force 覆盖。", file=sys.stderr)
            return 1

    # 写入分镜文件（每个分镜一个文件夹）
    for i, shot_data in enumerate(shots):
        shot_id = f"{i + 1:03d}"
        shot_dir = shots_dir / f"shot_{shot_id}"
        shot_dir.mkdir(parents=True, exist_ok=True)
        filepath = shot_dir / "shot.yaml"
        write_shot_yaml(filepath, shot_data, shot_id, args.chapter, char_map, scene_map)
        print(f"已生成: {filepath}")

    # 生成成功后删除 shots.json
    shots_json_path.unlink()

    print(f"\n✅ 共生成 {len(shots)} 个分镜")
    print(f"   目录: {shots_dir}")
    return 0
