#!/usr/bin/env python3
"""分镜首帧生成 — 按 shot YAML 的 keyframe_prompt 生成 keyframe.png，不跑视频

用法：
  vcshort gen-keyframe <项目路径> --chapter <章节号> --shot <分镜号> [--force]

示例：
  vcshort gen-keyframe /path/to/project --chapter ch01 --shot 001

流程：
  1. 读取 shot YAML（keyframe_prompt、characters、scene）
  2. 已有 keyframe.png 时直接返回（--force 时覆盖）
  3. 参考图：本镜角色图 + 首张场景图（保身份和地理）
  4. 调用图片 API 生成首帧图，存为 keyframe.png
  5. 生成失败不阻断，返回非零退出码供调用方判断
"""

import argparse
import sys
from pathlib import Path

from .gen_video import load_config, load_shot, ensure_keyframe


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="vcshort gen-keyframe",
        description="按分镜 keyframe_prompt 生成首帧图（不生成视频）",
    )
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--shot", required=True, help="分镜号（如 001_01 或 001）")
    parser.add_argument("--force", action="store_true", help="覆盖已有 keyframe.png")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    shot_dir = project_root / "chapters" / args.chapter / "shots" / f"shot_{args.shot}"
    shot_path = shot_dir / "shot.yaml"
    shot = load_shot(shot_path)
    config = load_config(project_root)

    keyframe_path = shot_dir / "keyframe.png"
    if keyframe_path.exists() and not args.force:
        print(f"分镜 {args.shot} 已有首帧图: {keyframe_path}")
        print("（如需重新生成，加 --force 覆盖）")
        return 0

    if keyframe_path.exists() and args.force:
        keyframe_path.unlink()
        print(f"已删除旧首帧图，重新生成: {keyframe_path}")

    keyframe_prompt = (shot.get("keyframe_prompt") or "").strip()
    if not keyframe_prompt:
        print(f"错误：shot YAML 无 keyframe_prompt，无法生成首帧图: {shot_path}", file=sys.stderr)
        return 1

    result = ensure_keyframe(shot, project_root, config, shot_dir)
    if result and result.exists():
        print(f"\n✅ 分镜 {args.shot} 首帧图生成完成")
        print(f"   首帧图: {result}")
        print("   确认满意后可用 /vc-short:gen-video 生成视频（会自动使用此首帧图）")
        return 0

    print(f"\n❌ 分镜 {args.shot} 首帧图生成失败", file=sys.stderr)
    print("   请检查 api.api_key 配置或网络连接", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
