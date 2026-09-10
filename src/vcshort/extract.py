#!/usr/bin/env python3
"""资产提取 — 从章节小说原文提取角色/场景，与 assets 目录匹配

用法：
  # 第一步：匹配，生成 tmp 文件（含 matched 字段，供用户确认）
  vcshort extract <项目路径> --chapter <章节号>

  # 第二步：用户确认后，生成 map 文件，删除 tmp
  vcshort extract <项目路径> --chapter <章节号> --confirm

流程：
  1. LLM 分析 novel.md，生成 extract.tmp.json（角色/场景 + 描述）
  2. extract 读取 extract.tmp.json，与 assets 目录已有资产匹配，写回 matched 字段
  3. LLM 展示匹配结果，用户逐个确认（填已有 key / 留空注册新的 / 删掉跳过）
  4. LLM 更新 extract.tmp.json 中的 matched 字段
  5. extract --confirm 读取 extract.tmp.json，生成 map 文件，删除 tmp

约定：
  - 角色资产目录：assets/characters/<角色名>/
  - 场景资产目录：assets/scenes/<场景名>/
  - 不再往 config.yaml 注册角色/场景，图片路径由目录约定推断
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

    unmatched_chars = sum(1 for c in (extract_data.get("characters") or []) if not c.get("matched"))
    unmatched_scenes = sum(1 for s in (extract_data.get("scenes") or []) if not s.get("matched"))
    total = unmatched_chars + unmatched_scenes

    if total:
        print(f"\n⚠️  {total} 个未匹配（角色 {unmatched_chars}，场景 {unmatched_scenes}）")
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
                char_yaml["appearance"] = char.get("description", "")
                voice_map = CommentedMap()
                voice_map["speaker"] = ""
                # instruction 由 LLM 在 extract.tmp.json 中提供，未提供则留空
                voice_map["instruction"] = char.get("instruction", "") or ""
                char_yaml["voice"] = voice_map
                with open(char_yaml_path, "w", encoding="utf-8") as f:
                    f.write("# 角色档案 — 生成图片/音色时读取\n")
                    f.write("# gender: male / female（必填，影响音色选择）\n")
                    f.write("# appearance: 外貌描述，gen-image 用\n")
                    f.write("# voice.speaker: 音色 ID，留空则按 gender 随机选\n")
                    f.write("# voice.instruction: 自然语言情感指令，如 \"用凶狠霸道的语气说\"\n\n")
                    yaml.dump(char_yaml, f)
                print(f"  已生成档案: {char_yaml_path}")

    char_map_path = chapter_dir / "character_map.yaml"
    with open(char_map_path, "w", encoding="utf-8") as f:
        f.write("# 角色映射 — 小说角色名 → assets 目录名\n")
        f.write("# 支持多形态：值填 角色名:形态名（如 小帅:女装）\n\n")
        yaml.dump(char_map, f)
    print(f"已生成: {char_map_path}")

    # --- 生成 scene_map.yaml ---
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

    scene_map_path = chapter_dir / "scene_map.yaml"
    with open(scene_map_path, "w", encoding="utf-8") as f:
        f.write("# 场景映射 — 小说场景描述 → assets 目录名\n\n")
        yaml.dump(scene_map, f)
    print(f"已生成: {scene_map_path}")

    total = new_chars + new_scenes
    print(f"\n✅ 完成")
    print(f"   新增资产: {total}（角色 +{new_chars}，场景 +{new_scenes}）")
    print(f"   map 文件: {char_map_path}, {scene_map_path}")
    if total:
        print("\n新增资产需要用 /gen-image 生成图片：")
        print("  角色：/gen-image --type character --name <角色名> --form <形态名> --prompt \"<描述>\"")
        print("  场景：/gen-image --type scene --name <场景名> --prompt \"<描述>\"")

    # 删除 tmp 文件
    extract_json_path.unlink()
    print(f"   已清理临时文件: {extract_json_path.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort extract", description="从小说原文提取资产并与 assets 目录匹配")
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
