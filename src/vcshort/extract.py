#!/usr/bin/env python3
"""资产提取 — 从剧本提取角色/场景/道具，与 assets 目录匹配

用法：
  # 第一步：匹配，生成 tmp 文件（含 matched 字段，供用户确认）
  vcshort extract <项目路径> --chapter <章节号>

  # 第二步：用户确认后，生成 map 文件，删除 tmp
  vcshort extract <项目路径> --chapter <章节号> --confirm

流程：
  1. LLM 读 script.md 提取角色/场景/道具清单，缺描述时 grep novel.md 搜名字+前后N行补描述
  2. LLM 生成 extract.tmp.json（characters + scenes + props + 描述）
  3. extract 读取 extract.tmp.json，与 assets 目录已有资产匹配，写回 matched 字段
  4. LLM 展示匹配结果，用户逐个确认（填已有 key / 留空注册新的 / 删掉跳过）
  5. LLM 更新 extract.tmp.json 中的 matched 字段
  6. extract --confirm 读取 extract.tmp.json，生成 map 文件 + asset yaml，删除 tmp

约定：
  - 角色资产目录：assets/characters/<角色名>/character.yaml
  - 场景资产目录：assets/scenes/<场景名>/scene.yaml
  - 道具资产目录：assets/props/<道具名>/prop.yaml
  - 不再往 config.yaml 注册资产，图片路径由目录约定推断
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

from .gen_image import build_prompt as build_image_prompt


def load_style_config(project_root: Path) -> dict:
    """读取 config.yaml 的 style / aspect_ratio，供拼接完整提示词用。"""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        return {"style": None, "aspect_ratio": None}
    yaml_loader = YAML()
    yaml_loader.allow_unicode = True
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml_loader.load(f) or {}
    return {"style": cfg.get("style"), "aspect_ratio": cfg.get("aspect_ratio")}


def scan_existing_characters(project_root: Path) -> list:
    """扫描 assets/characters/ 目录，返回已有角色名列表。"""
    char_dir = project_root / "assets" / "characters"
    if not char_dir.is_dir():
        return []
    return sorted([d.name for d in char_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])


def scan_existing_scenes(project_root: Path) -> list:
    """扫描 assets/scenes/ 目录，返回已有场景名列表。"""
    scene_dir = project_root / "assets" / "scenes"
    if not scene_dir.is_dir():
        return []
    return sorted([d.name for d in scene_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])


def scan_existing_props(project_root: Path) -> list:
    """扫描 assets/props/ 目录，返回已有道具名列表。"""
    prop_dir = project_root / "assets" / "props"
    if not prop_dir.is_dir():
        return []
    return sorted([d.name for d in prop_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])


def fuzzy_match(name: str, keys) -> str:
    """精确匹配 + 模糊匹配（包含关系）。"""
    if name in keys:
        return name
    for key in keys:
        if name in key or key in name:
            return key
    return ""


def do_match(project_root: Path, chapter: str) -> None:
    """读取 extract.tmp.json，与 assets 目录已有资产匹配，写回 matched 字段。"""
    chapter_dir = project_root / "chapters" / chapter
    extract_json_path = chapter_dir / "extract.tmp.json"
    if not extract_json_path.exists():
        print(f"错误：{extract_json_path} 不存在", file=sys.stderr)
        print("请先让 LLM 分析 novel.md 并生成 extract.tmp.json", file=sys.stderr)
        sys.exit(1)

    with open(extract_json_path, encoding="utf-8") as f:
        extract_data = json.load(f)

    existing_chars = scan_existing_characters(project_root)
    existing_scenes = scan_existing_scenes(project_root)
    existing_props = scan_existing_props(project_root)

    # 匹配角色
    for char in extract_data.get("characters") or []:
        name = char.get("name", "")
        matched = fuzzy_match(name, existing_chars)
        # 检查形态匹配
        forms = char.get("forms") or []
        if matched and forms:
            char_dir = project_root / "assets" / "characters" / matched
            config_form_names = []
            if char_dir.is_dir():
                # 扫描 <角色名>-<形态>.png 形式的文件
                for p in char_dir.iterdir():
                    stem = p.stem
                    if stem == matched:
                        config_form_names.append("默认")
                    elif stem.startswith(f"{matched}-"):
                        config_form_names.append(stem[len(matched) + 1:])
            for form in forms:
                form_name = form.get("name", "")
                form_match = fuzzy_match(form_name, config_form_names)
                if form_match and form_match != "默认":
                    matched = f"{matched}:{form_match}"
                    break
        char["matched"] = matched

    # 匹配场景
    for scene in extract_data.get("scenes") or []:
        name = scene.get("name", "")
        scene["matched"] = fuzzy_match(name, existing_scenes)

    # 匹配道具
    for prop in extract_data.get("props") or []:
        name = prop.get("name", "")
        prop["matched"] = fuzzy_match(name, existing_props)

    # 写回 extract.tmp.json
    with open(extract_json_path, "w", encoding="utf-8") as f:
        json.dump(extract_data, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("匹配结果:\n")
    print("角色:")
    for char in extract_data.get("characters") or []:
        name = char.get("name", "")
        matched = char.get("matched", "")
        forms = char.get("forms") or []
        forms_info = ""
        if forms:
            form_names = ", ".join(f.get("name", "") for f in forms)
            forms_info = f"（形态: {form_names}）"
        status = f"→ {matched} ✅" if matched else "❌ 未匹配"
        print(f"  {name} {forms_info} {status}")

    print("\n场景:")
    for scene in extract_data.get("scenes") or []:
        name = scene.get("name", "")
        matched = scene.get("matched", "")
        status = f"→ {matched} ✅" if matched else "❌ 未匹配"
        print(f"  {name} {status}")

    print("\n道具:")
    for prop in extract_data.get("props") or []:
        name = prop.get("name", "")
        matched = prop.get("matched", "")
        status = f"→ {matched} ✅" if matched else "❌ 未匹配"
        print(f"  {name} {status}")

    unmatched_chars = sum(1 for c in (extract_data.get("characters") or []) if not c.get("matched"))
    unmatched_scenes = sum(1 for s in (extract_data.get("scenes") or []) if not s.get("matched"))
    unmatched_props = sum(1 for p in (extract_data.get("props") or []) if not p.get("matched"))
    total = unmatched_chars + unmatched_scenes + unmatched_props

    if total:
        print(f"\n⚠️  {total} 个未匹配（角色 {unmatched_chars}，场景 {unmatched_scenes}，道具 {unmatched_props}）")
        print("请确认 extract.tmp.json 中的 matched 字段：")
        print("  - 填入已有的 assets 目录名进行手动匹配")
        print('  - 保持空字符串 "" 则注册为新资产（用 /gen-image 生成图片即可）')
        print("  - 删掉不需要的条目")
        print(f"\n确认后运行: vcshort extract {project_root} --chapter {chapter} --confirm")
    else:
        print("\n✅ 所有资产已匹配")
        print(f"运行: vcshort extract {project_root} --chapter {chapter} --confirm 生成 map 文件")


def do_confirm(project_root: Path, chapter: str) -> None:
    """读取确认后的 extract.tmp.json，生成 map 文件，删除 tmp。"""
    chapter_dir = project_root / "chapters" / chapter
    extract_json_path = chapter_dir / "extract.tmp.json"
    if not extract_json_path.exists():
        print(f"错误：{extract_json_path} 不存在", file=sys.stderr)
        sys.exit(1)

    with open(extract_json_path, encoding="utf-8") as f:
        extract_data = json.load(f)

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096

    new_chars = 0
    new_scenes = 0

    # 加载 style 配置，供拼接角色完整提示词
    style_config = load_style_config(project_root)

    # --- 生成 character_map.yaml + character.yaml ---
    char_map = CommentedMap()
    for char in extract_data.get("characters") or []:
        name = char.get("name", "")
        matched = char.get("matched", "")

        if not matched and name:
            # 新角色：用角色名作为 assets 目录名，映射到自身
            char_map[name] = name
            new_chars += 1
            print(f"  新增角色: {name}（用 /gen-image 生成图片）")
        else:
            char_map[name] = matched

        # 为每个角色生成 character.yaml 档案（新角色和已匹配角色都生成）
        # 已匹配角色若已有 character.yaml 则不覆盖
        char_dir_name = matched if matched else name
        if char_dir_name:
            char_dir = project_root / "assets" / "characters" / char_dir_name
            char_yaml_path = char_dir / "character.yaml"
            char_dir.mkdir(parents=True, exist_ok=True)
            if not char_yaml_path.exists():
                char_yaml = CommentedMap()
                char_yaml["name"] = name
                # gender 由 LLM 在 extract.tmp.json 中提供（male/female），未提供则留空
                char_yaml["gender"] = char.get("gender", "") or ""
                # 用 extract.tmp.json 里的 description 填 appearance
                appearance = char.get("description", "") or ""
                char_yaml["appearance"] = appearance
                # personality 独立字段：性格描述，从言行决策推断
                personality = char.get("personality", "") or ""
                char_yaml["personality"] = personality
                voice_map = CommentedMap()
                voice_map["speaker"] = ""
                # instruction 由 LLM 在 extract.tmp.json 中提供，未提供则留空
                voice_map["instruction"] = char.get("instruction", "") or ""
                char_yaml["voice"] = voice_map
                # 完整提示词（与 gen-image 调 API 时提交的 prompt 一致，可直接粘贴到豆包 seedream 网页对话框）
                # 角色类型默认带1张参考图引用（"参考图1的风格"），手动上传1张已有角色图保画风一致
                full_prompt = build_image_prompt(appearance, style_config, "character") if appearance else ""
                char_yaml["full_prompt"] = full_prompt
                with open(char_yaml_path, "w", encoding="utf-8") as f:
                    f.write("# 角色档案 — 生成图片/音色时读取\n")
                    f.write("# gender: male / female（必填，影响音色选择）\n")
                    f.write("# appearance: 外貌描述，gen-image 用\n")
                    f.write("# personality: 性格描述，从言行决策推断\n")
                    f.write("# full_prompt: 完整提示词，可直接粘贴到豆包 seedream 网页对话框\n")
                    f.write('#   生成时手动上传1张已有角色图当参考图（对应提示词里的"参考图1"）\n')
                    f.write("# voice.speaker: 音色 ID，留空则按 gender 随机选\n")
                    f.write("# voice.instruction: 自然语言情感指令，如 \"用凶狠霸道的语气说\"\n\n")
                    yaml.dump(char_yaml, f)
                print(f"  已生成档案: {char_yaml_path}")

    char_map_path = chapter_dir / "character_map.yaml"
    with open(char_map_path, "w", encoding="utf-8") as f:
        f.write("# 角色映射 — 剧本角色名 → assets 目录名\n")
        f.write("# 支持多形态：值填 角色名:形态名（如 小帅:女装）\n\n")
        yaml.dump(char_map, f)
    print(f"已生成: {char_map_path}")

    # --- 生成 scene_map.yaml + scene.yaml ---
    scene_map = CommentedMap()
    for scene in extract_data.get("scenes") or []:
        name = scene.get("name", "")
        matched = scene.get("matched", "")

        if not matched and name:
            # 新场景：用场景名作为 assets 目录名，映射到自身
            scene_map[name] = name
            new_scenes += 1
            print(f"  新增场景: {name}（用 /gen-image 生成图片）")
        else:
            scene_map[name] = matched

        # 为每个场景生成 scene.yaml 档案（已存在则不覆盖）
        scene_dir_name = matched if matched else name
        if scene_dir_name:
            scene_dir = project_root / "assets" / "scenes" / scene_dir_name
            scene_yaml_path = scene_dir / "scene.yaml"
            scene_dir.mkdir(parents=True, exist_ok=True)
            if not scene_yaml_path.exists():
                scene_yaml = CommentedMap()
                scene_yaml["name"] = name
                scene_yaml["description"] = scene.get("description", "") or ""
                with open(scene_yaml_path, "w", encoding="utf-8") as f:
                    f.write("# 场景档案 — 生成图片时读取\n")
                    f.write("# description: 场景描述，gen-image 用\n\n")
                    yaml.dump(scene_yaml, f)
                print(f"  已生成档案: {scene_yaml_path}")

    scene_map_path = chapter_dir / "scene_map.yaml"
    with open(scene_map_path, "w", encoding="utf-8") as f:
        f.write("# 场景映射 — 剧本场景描述 → assets 目录名\n\n")
        yaml.dump(scene_map, f)
    print(f"已生成: {scene_map_path}")

    # --- 生成 prop_map.yaml + prop.yaml ---
    new_props = 0
    prop_map = CommentedMap()
    for prop in extract_data.get("props") or []:
        name = prop.get("name", "")
        matched = prop.get("matched", "")

        if not matched and name:
            # 新道具：用道具名作为 assets 目录名，映射到自身
            prop_map[name] = name
            new_props += 1
            print(f"  新增道具: {name}（用 /gen-image 生成图片）")
        else:
            prop_map[name] = matched

        # 为每个道具生成 prop.yaml 档案（已存在则不覆盖）
        prop_dir_name = matched if matched else name
        if prop_dir_name:
            prop_dir = project_root / "assets" / "props" / prop_dir_name
            prop_yaml_path = prop_dir / "prop.yaml"
            prop_dir.mkdir(parents=True, exist_ok=True)
            if not prop_yaml_path.exists():
                prop_yaml = CommentedMap()
                prop_yaml["name"] = name
                prop_yaml["description"] = prop.get("description", "") or ""
                prop_yaml["owner"] = prop.get("owner", "") or ""
                with open(prop_yaml_path, "w", encoding="utf-8") as f:
                    f.write("# 道具档案 — 生成图片和跨镜连续性跟踪用\n")
                    f.write("# description: 道具描述，gen-image 用\n")
                    f.write("# owner: 持有者角色名，可为空（公共道具）\n\n")
                    yaml.dump(prop_yaml, f)
                print(f"  已生成档案: {prop_yaml_path}")

    prop_map_path = chapter_dir / "prop_map.yaml"
    with open(prop_map_path, "w", encoding="utf-8") as f:
        f.write("# 道具映射 — 剧本道具名 → assets 目录名\n\n")
        yaml.dump(prop_map, f)
    print(f"已生成: {prop_map_path}")

    total = new_chars + new_scenes + new_props
    print(f"\n✅ 完成")
    print(f"   新增资产: {total}（角色 +{new_chars}，场景 +{new_scenes}，道具 +{new_props}）")
    print(f"   map 文件: {char_map_path}, {scene_map_path}, {prop_map_path}")
    if total:
        print("\n新增资产需要用 /gen-image 生成图片：")
        print("  角色：/gen-image --type character --name <角色名> --form <形态名> --prompt \"<描述>\"")
        print("  场景：/gen-image --type scene --name <场景名> --prompt \"<描述>\"")
        print("  道具：/gen-image --type prop --name <道具名> --prompt \"<描述>\"")

    # 删除 tmp 文件
    extract_json_path.unlink()
    print(f"   已清理临时文件: {extract_json_path.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort extract", description="从剧本提取资产（角色/场景/道具）并与 assets 目录匹配")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--confirm", action="store_true", help="用户确认后，生成 map 文件")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    if args.confirm:
        do_confirm(project_root, args.chapter)
    else:
        do_match(project_root, args.chapter)
    return 0
