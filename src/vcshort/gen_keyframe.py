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

from .gen_video import load_config, load_shot, find_character_image, find_scene_images, find_prop_image


def prev_shot_id(project_root: Path, chapter: str, shot_num: str) -> str | None:
    """计算上一个分镜的 shot_id。
    shot_num 格式为 "主号_子号"（如 "001_02"）或纯数字（如 "001"）。
    - 同主号的上一子号（如 001_02 → 001_01）
    - 如果是第一个子号（如 001_01），找上一个主号的最后一个子号（如 001_01 → 002_03）
    - 纯数字格式按原逻辑处理（001 → 000）
    """
    if "_" in shot_num:
        main, sub = shot_num.split("_", 1)
        sub_num = int(sub)
        if sub_num > 1:
            # 同主号上一子号
            prev_id = f"{main}_{sub_num - 1:02d}"
        else:
            # 第一个子号，找上一个主号的最后一个子号
            prev_main = int(main) - 1
            if prev_main < 1:
                return None
            prev_main_str = f"{prev_main:03d}"
            # 找上一个主号下所有子号，取最大的
            shots_dir = project_root / "chapters" / chapter / "shots"
            prev_subs = []
            if shots_dir.is_dir():
                for d in shots_dir.iterdir():
                    if d.is_dir() and d.name.startswith(f"shot_{prev_main_str}_"):
                        sub_part = d.name.replace(f"shot_{prev_main_str}_", "")
                        if sub_part.isdigit():
                            prev_subs.append(int(sub_part))
            if not prev_subs:
                return None
            prev_id = f"{prev_main_str}_{max(prev_subs):02d}"
    else:
        # 纯数字格式（兼容旧分镜）
        prev_num = int(shot_num) - 1
        if prev_num < 1:
            return None
        prev_id = f"{prev_num:03d}"

    return prev_id


# 首帧来源标记可引用的帧图文件；标记只写镜位不写帧型时，由调用方指定（gen-keyframe 时 agent 看实际帧图选）
_FRAME_FILES = {"尾帧": "last_frame.png", "首帧": "keyframe.png", "第一帧": "first_frame.png"}
_FRAME_LABELS = {"尾帧": "结尾画面", "首帧": "首帧画面", "第一帧": "第一帧画面"}
_SHOT_OFFSETS = {"上一镜": 1, "上两镜": 2, "上上镜": 2, "上三镜": 3, "上上上镜": 3}


def resolve_frame_anchor(project_root: Path, chapter: str, shot_num: str, keyframe_source: str, frame_kind: str = None) -> tuple:
    """把首帧来源标记解析成锚点图路径，返回 (路径或None, 提示词里的引用描述或None)。

    标记格式：`<镜位>[<帧型>]` 或 `参考前帧`，如：
      参考前帧        → 意图标记：本镜首帧需要参考前面的帧图，具体帧型由 frame_kind 参数定，镜位默认上一镜
      上一镜          → 上一分镜的帧图（帧型由 frame_kind 参数定）
      上一镜首帧      → 上一分镜 keyframe.png（标记里显式指定帧型时优先于 frame_kind）
      上上镜尾帧      → 往前数第2镜的 last_frame.png
      shot_001_02第一帧 → 显式指定分镜的 first_frame.png
    镜位或帧型缺失、无法解析时返回 (None, None)。路径不要求文件存在（编译期预览用）。
    """
    import re
    m = re.match(r"^(参考前帧|上一镜|上两镜|上上镜|上三镜|上上上镜|shot_\d+(?:_\d+)?)(尾帧|首帧|第一帧)?",
                 (keyframe_source or "").strip())
    if not m:
        return None, None
    ref, kind = m.group(1), m.group(2) or frame_kind
    if ref == "参考前帧":
        ref = "上一镜"
    if not kind:
        return None, None
    if ref.startswith("shot_"):
        target_id = ref[5:]
    else:
        target_id = shot_num
        for _ in range(_SHOT_OFFSETS[ref]):
            target_id = prev_shot_id(project_root, chapter, target_id)
            if not target_id:
                return None, None
    path = project_root / "chapters" / chapter / "shots" / f"shot_{target_id}" / _FRAME_FILES[kind]
    label = f"{'shot_' + target_id if ref.startswith('shot_') else ref}的{_FRAME_LABELS[kind]}"
    return path, label


def apply_anchor_override(keyframe_source: str, anchor_override: str) -> str:
    """gen-keyframe 运行期 --anchor 参数换算成首帧来源标记。

    - "none"/"无"/"不参考" → 不用锚点
    - 帧型词（尾帧/首帧/第一帧）→ 沿用标记里的镜位，只换帧型（无标记时默认上一镜）
    - 完整标记（上一镜首帧/shot_001_02尾帧 等）→ 整体覆盖
    """
    if not anchor_override:
        return keyframe_source
    if anchor_override in ("none", "无", "不参考"):
        return ""
    if anchor_override in _FRAME_FILES:
        import re
        m = re.match(r"^(上一镜|上两镜|上上镜|上三镜|上上上镜|shot_\d+(?:_\d+)?)", keyframe_source or "")
        return (m.group(1) if m else "上一镜") + anchor_override
    return anchor_override


def prev_last_frame_path(project_root: Path, chapter: str, shot_num: str) -> Path | None:
    """上一个分镜 last_frame.png 的期望路径（兼容旧调用）。"""
    prev_id = prev_shot_id(project_root, chapter, shot_num)
    if not prev_id:
        return None
    return project_root / "chapters" / chapter / "shots" / f"shot_{prev_id}" / "last_frame.png"


def find_prev_last_frame(project_root: Path, chapter: str, shot_num: str) -> Path | None:
    """查找上一个分镜的 last_frame.png（文件不存在则返回 None），用于保持分镜间连贯性。"""
    prev_frame = prev_last_frame_path(project_root, chapter, shot_num)
    if prev_frame and prev_frame.exists():
        return prev_frame
    return None


def build_continuity_keyframe_prompt(shot: dict, project_root: Path, config: dict, prev_frame: Path, source_label: str = "上一镜的结尾画面") -> tuple:
    """拼接「首帧来源=帧图锚点」的提示词与参考图列表。

    图1锚定场景陈设、光线、人物身份和道具；站位、姿态、持物一律按 keyframe_prompt
    描述为准（不再区分严格/调整模式）。

    参考图：图1=锚点帧图（连续性锚点）+ 本镜角色图（换机位需重绘未见过的一面，保身份）+ 场景图（保地理）+ 道具图（保外观）。
    返回 (final_prompt, ref_images)，ref_images 按 @图N 顺序排列。
    gen_shots 编译期与 ensure_keyframe 运行期共用，保证 YAML 预览与实发提示词一致。
    """
    keyframe_prompt = (shot.get("keyframe_prompt") or "").strip()
    ref_images = [str(prev_frame)]
    ref_lines = [f"{source_label}@图1"]
    img_idx = 2
    for char_item in shot.get("characters") or []:
        char_name = char_item.get("name", "")
        char_name_clean = char_name.split(":")[0] if ":" in char_name else char_name
        form_name = char_name.split(":")[1] if ":" in char_name else "默认"
        img = find_character_image(project_root, char_name_clean, form_name)
        if img:
            ref_images.append(str(img))
            ref_lines.append(f"{char_name_clean}形象@图{img_idx}")
            img_idx += 1
    scene_key = shot.get("scene")
    if scene_key:
        scene_imgs = find_scene_images(project_root, scene_key)
        if scene_imgs:
            ref_images.append(str(scene_imgs[0]))
            ref_lines.append(f"{scene_key}场景@图{img_idx}")
            img_idx += 1
    prop_ref_added = False
    for prop_item in shot.get("props") or []:
        prop_name = prop_item.get("name", "") if isinstance(prop_item, dict) else prop_item
        if not prop_name:
            continue
        prop_img = find_prop_image(project_root, prop_name)
        if prop_img:
            ref_images.append(str(prop_img))
            ref_lines.append(f"{prop_name}外观@图{img_idx}")
            img_idx += 1
            prop_ref_added = True

    camera = shot.get("camera") or {}
    cam_desc = "·".join(x for x in [camera.get("shot_type"), camera.get("angle")] if x) or "新机位"
    # 景别→明确裁切范围，防止参考图锚定构图导致换镜不换景别
    crop_hint = {
        "特写": "画面裁到肩部以上，聚焦面部",
        "近景": "画面裁到胸部以上",
        "中景": "画面裁到腰部或膝盖以上",
        "全景": "画面含人物全身和周围环境",
        "远景": "人物在画面中小，环境为主",
    }.get(camera.get("shot_type"), "")

    picture_line = f"画面：{keyframe_prompt}"
    constraint_line = ("约束：场景陈设、光线与图1保持一致；人物站位、姿态、持物按画面描述为准；"
                       "不新增画面描述之外的人物和道具；人物五官、发型、服饰与角色参考图严格一致")
    if prop_ref_added:
        constraint_line += "；道具外观与道具参考图严格一致"

    style = config.get("style")
    aspect = config.get("aspect_ratio")
    lines = [
        "参考：" + "，".join(ref_lines),
        f"镜头：这是同一场景的下一个镜头，构图必须变化——按{cam_desc}取景，{crop_hint + '，' if crop_hint else ''}禁止复用图1的取景范围和角度",
        picture_line,
        constraint_line,
        "用途：作为图生视频的起始画面",
    ]
    if style:
        lines.append(f"风格：{style}风格")
    if aspect:
        lines.append(f"比例：{aspect}构图")
    return "\n".join(lines), ref_images


def ensure_keyframe(shot: dict, project_root: Path, config: dict, shot_dir: Path, anchor_override: str = None) -> Path | None:
    """按 keyframe_prompt 生成首帧图（keyframe.png），已存在则直接返回。

    参考图：本镜角色图 + 场景图，保身份和地理。生成失败不阻断视频流程。
    """
    keyframe_path = shot_dir / "keyframe.png"
    if keyframe_path.exists():
        return keyframe_path

    keyframe_prompt = (shot.get("keyframe_prompt") or "").strip()
    if not keyframe_prompt:
        print("提示：shot YAML 无 keyframe_prompt，跳过首帧图生成", file=sys.stderr)
        return None

    from .gen_image import generate_image, download_image, DEFAULT_BASE_URL, DEFAULT_MODEL

    api_cfg = config.get("api") or {}
    if not api_cfg.get("api_key"):
        print("警告：未配置 api.api_key，跳过首帧图生成", file=sys.stderr)
        return None
    api_config = {
        "api_key": api_cfg.get("api_key"),
        "base_url": api_cfg.get("base_url", DEFAULT_BASE_URL),
        "image_model": api_cfg.get("image_model", DEFAULT_MODEL),
    }

    # 首帧来源标记（参考前帧 / 上一镜尾帧 / shot_001_02首帧 等）：
    # 以解析到的帧图为图1连续性锚点，场景陈设/光线/身份/道具延续图1，站位/姿态/持物按 keyframe_prompt 为准。
    # --anchor 参数可在运行期覆盖/指定具体帧图；标记只给镜位或「参考前帧」时默认尾帧
    keyframe_source = apply_anchor_override((shot.get("keyframe_source") or "").strip(), anchor_override)
    anchor, anchor_label = resolve_frame_anchor(
        project_root, shot.get("chapter") or "", shot.get("shot_id") or "", keyframe_source, frame_kind="尾帧")
    if keyframe_source and anchor is None:
        print(f"提示：首帧来源标记「{keyframe_source}」无法解析，按文本提示词生成首帧")
    if anchor is not None:
        if anchor.exists():
            final_prompt, ref_images = build_continuity_keyframe_prompt(
                shot, project_root, config, anchor, anchor_label)
            print(f"分镜标注首帧来源={keyframe_source}，锚点: {anchor}")
            print("正在生成首帧图（切镜头重新构图，状态按画面描述调整）...")
            print(f"提示词: {final_prompt}")
            try:
                image_url = generate_image(final_prompt, api_config, size="2K", ref_images=ref_images)
                download_image(image_url, keyframe_path)
            except SystemExit:
                print("警告：首帧图生成失败，继续用文本提示词生成视频", file=sys.stderr)
                return None
            print(f"已保存首帧图: {keyframe_path}")
            return keyframe_path
        else:
            print(f"提示：分镜标注首帧来源={keyframe_source}，但 {anchor} 尚不存在（上游未生成），按文本提示词生成首帧")

    # 参考图：角色图（保身份）+ 首张场景图（保地理）+ 道具图（保外观）
    ref_images = []
    ref_descriptions = []
    for char_item in shot.get("characters") or []:
        char_name = char_item.get("name", "")
        char_name_clean = char_name.split(":")[0] if ":" in char_name else char_name
        form_name = char_name.split(":")[1] if ":" in char_name else "默认"
        img = find_character_image(project_root, char_name_clean, form_name)
        if img:
            ref_images.append(str(img))
            pos = char_item.get("position", "")
            desc = f"{char_name_clean}形象"
            if pos:
                desc += f"，{pos}"
            ref_descriptions.append(desc)
    scene_key = shot.get("scene")
    if scene_key:
        scene_imgs = find_scene_images(project_root, scene_key)
        if scene_imgs:
            ref_images.append(str(scene_imgs[0]))
            ref_descriptions.append(f"{scene_key}场景")
    for prop_item in shot.get("props") or []:
        prop_name = prop_item.get("name", "") if isinstance(prop_item, dict) else prop_item
        if not prop_name:
            continue
        prop_img = find_prop_image(project_root, prop_name)
        if prop_img:
            ref_images.append(str(prop_img))
            ref_descriptions.append(f"{prop_name}外观")

    style = config.get("style")
    aspect = config.get("aspect_ratio")
    from .gen_image import build_prompt
    final_prompt = build_prompt(
        keyframe_prompt,
        {"style": style, "aspect_ratio": aspect},
        "keyframe",
        ref_count=len(ref_images),
        ref_descriptions=ref_descriptions,
        shot_type=(shot.get("camera") or {}).get("shot_type"),
    )

    print("正在生成首帧图...")
    print(f"提示词: {final_prompt}")
    try:
        image_url = generate_image(final_prompt, api_config, size="2K", ref_images=ref_images or None)
        download_image(image_url, keyframe_path)
    except SystemExit:
        print("警告：首帧图生成失败，继续用文本提示词生成视频", file=sys.stderr)
        return None
    print(f"已保存首帧图: {keyframe_path}")
    return keyframe_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="vcshort gen-keyframe",
        description="按分镜 keyframe_prompt 生成首帧图（不生成视频）",
    )
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--shot", required=True, help="分镜号（如 001_01 或 001）")
    parser.add_argument("--force", action="store_true", help="覆盖已有 keyframe.png")
    parser.add_argument("--anchor", default=None,
                        help="首帧锚点覆盖：帧型（尾帧/首帧/第一帧，沿用标记镜位）、完整标记（上一镜首帧/shot_001_02尾帧）、none 不用锚点。shot 标了「参考前帧」时用此参数指定具体参考图")
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

    result = ensure_keyframe(shot, project_root, config, shot_dir, anchor_override=args.anchor)
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
