#!/usr/bin/env python3
"""资产查看 — 扫描 assets 目录列出已有角色/场景/服装/道具

用法：
  vcshort config-list <项目路径>

约定优于配置：资产信息由 assets 目录结构决定，不再维护 config.yaml。
  - 角色：assets/characters/<角色名>/，图片：<角色名>.png 或 <角色名>-<形态>.png
  - 场景：assets/scenes/<场景名>/，图片：1.png, 2.png, ...
  - 服装：assets/costumes/<服装名>.png
  - 道具：assets/props/<道具名>.png
"""

import argparse
import sys
from pathlib import Path


def list_characters(project_root: Path) -> None:
    """列出 assets/characters/ 下的角色。"""
    char_dir = project_root / "assets" / "characters"
    print("角色:")
    if not char_dir.is_dir():
        print("  (无)")
        return
    chars = sorted([d for d in char_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
    if not chars:
        print("  (无)")
        return
    for char_path in chars:
        name = char_path.name
        # 扫描形态：默认 <name>.png，其他 <name>-<form>.png
        forms = []
        for p in char_path.iterdir():
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            stem = p.stem
            if stem == name:
                forms.append("默认")
            elif stem.startswith(f"{name}-"):
                forms.append(stem[len(name) + 1:])
        forms_str = ", ".join(sorted(forms)) if forms else "(无图片)"
        print(f"  {name}（形态: {forms_str}）")


def list_scenes(project_root: Path) -> None:
    """列出 assets/scenes/ 下的场景。"""
    scene_dir = project_root / "assets" / "scenes"
    print("\n场景:")
    if not scene_dir.is_dir():
        print("  (无)")
        return
    scenes = sorted([d for d in scene_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
    if not scenes:
        print("  (无)")
        return
    for scene_path in scenes:
        name = scene_path.name
        imgs = [p for p in scene_path.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        print(f"  {name}（{len(imgs)} 张图片）")


def list_costumes(project_root: Path) -> None:
    """列出 assets/costumes/ 下的服装。"""
    costume_dir = project_root / "assets" / "costumes"
    print("\n服装:")
    if not costume_dir.is_dir():
        print("  (无)")
        return
    imgs = [p for p in costume_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    if not imgs:
        print("  (无)")
        return
    for p in sorted(imgs):
        print(f"  {p.stem}")


def list_props(project_root: Path) -> None:
    """列出 assets/props/ 下的道具。"""
    prop_dir = project_root / "assets" / "props"
    print("\n道具:")
    if not prop_dir.is_dir():
        print("  (无)")
        return
    imgs = [p for p in prop_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    if not imgs:
        print("  (无)")
        return
    for p in sorted(imgs):
        print(f"  {p.stem}")


def list_assets(args, project_root: Path):
    list_characters(project_root)
    list_scenes(project_root)
    list_costumes(project_root)
    list_props(project_root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort config-list", description="扫描 assets 目录列出已有资产")
    parser.add_argument("project", help="项目路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出所有资产")
    p_list.set_defaults(func=list_assets)

    args = parser.parse_args(argv)
    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    args.func(args, project_root)
    return 0
