#!/usr/bin/env python3
"""分镜拆分 — 从 Markdown 分镜文档生成 shot YAML 文件

用法：
  vcshort gen-shots <项目路径> --chapter <章节号> [--force]

LLM 按 drama 风格直接写 chapters/<章节号>/shots.md（## SHOT-XXX 块），
本脚本解析该 Markdown，生成 gen-video 消费的 shot YAML。

Markdown 分镜块格式：
  ## SHOT-001-01

  - 来源：SC001
  - 职责：展示...
  - 时长：10
  - 景别：中景
  - 机位：平视·固定
  - 角色：陈青源@大殿中央, 姚素素@左侧首位
  - 场景：玄青宗大殿
  - 唯一动作：陈青源逐一回应质疑
  - 终点：陈青源站定，师姐们神色各异

  ### 声音
  陈青源（拱手）：各位师姐，我确实是陈青源。

  ### 冻结关键帧提示词
  黑衣青年陈青源站在大殿中央，四周师姐围立

SHOT 编号：场序-镜序（如 1-1、2-3），解析后归一为 001_01、002_03。
"""

import argparse
import re
import sys
from pathlib import Path

from .gen_video import build_prompt_plan

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
except ImportError:
    print("错误：需要 ruamel.yaml，请运行 pip install ruamel.yaml", file=sys.stderr)
    sys.exit(1)


# ---------- 映射文件 ----------

def load_character_map(project_root: Path, chapter: str) -> dict:
    map_path = project_root / "chapters" / chapter / "character_map.yaml"
    if not map_path.exists():
        return {}
    yaml = YAML()
    yaml.allow_unicode = True
    with open(map_path, encoding="utf-8") as f:
        data = yaml.load(f) or {}
    return dict(data)


def load_scene_map(project_root: Path, chapter: str) -> dict:
    map_path = project_root / "chapters" / chapter / "scene_map.yaml"
    if not map_path.exists():
        return {}
    yaml = YAML()
    yaml.allow_unicode = True
    with open(map_path, encoding="utf-8") as f:
        data = yaml.load(f) or {}
    return dict(data)


def load_prop_map(project_root: Path, chapter: str) -> dict:
    map_path = project_root / "chapters" / chapter / "prop_map.yaml"
    if not map_path.exists():
        return {}
    yaml = YAML()
    yaml.allow_unicode = True
    with open(map_path, encoding="utf-8") as f:
        data = yaml.load(f) or {}
    return dict(data)


def _char_name(char_item) -> str:
    return char_item.get("name", "")


def map_characters(characters: list, char_map: dict) -> list:
    result = []
    for char in characters:
        name = char.get("name", "")
        mapped = char_map.get(name, name)
        out = CommentedMap()
        out["name"] = mapped
        position = char.get("position")
        if position:
            out["position"] = position
        result.append(out)
    return result


def map_scene(scene: str, scene_map: dict) -> str:
    if scene:
        return scene_map.get(scene, scene)
    return scene


def map_props(props: list, prop_map: dict) -> list:
    """将剧本道具名映射为 assets 目录名。

    输入：["玉镯", "信件"] 或 [{"name": "玉镯", "state": "在陈青源手中"}]
    输出：[{"name": "玉镯", "state": "..."}]（name 映射后）
    """
    result = []
    for prop in props or []:
        if isinstance(prop, str):
            name = prop
            state = ""
        else:
            name = prop.get("name", "")
            state = prop.get("state", "")
        mapped = prop_map.get(name, name)
        out = CommentedMap()
        out["name"] = mapped
        if state:
            out["state"] = state
        result.append(out)
    return result


# ---------- Markdown 解析 ----------

SHOT_HEADER_RE = re.compile(r"^##\s+SHOT-(\d+)-(\d+)\s*$", re.MULTILINE)
SUBHEAD_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def parse_characters(field_value: str) -> list:
    """解析 '角色名@位置, 角色名@位置' 为 [{"name":..., "position":...}]。"""
    result = []
    for item in field_value.split(","):
        item = item.strip()
        if not item:
            continue
        if "@" in item:
            name, position = item.split("@", 1)
            result.append({"name": name.strip(), "position": position.strip()})
        else:
            result.append({"name": item, "position": ""})
    return result


def parse_camera(shot_type: str, placement: str, duration: str) -> dict:
    """解析景别、机位、时长为 camera dict。

    机位格式 '平视·固定' → angle=平视, movement=固定；
    单词 '平视' → angle=平视, movement=固定（默认）。
    """
    angle = "平视"
    movement = "固定"
    if placement:
        if "·" in placement:
            parts = [p.strip() for p in placement.split("·")]
            angle = parts[0] or angle
            if len(parts) > 1 and parts[1]:
                movement = parts[1]
        else:
            angle = placement.strip() or angle
    try:
        dur = int(duration) if duration else 15
    except ValueError:
        dur = 15
    if dur not in (5, 10, 15):
        # 归一到最接近的合法档
        dur = 15 if dur > 10 else (10 if dur > 5 else 5)
    return {"shot_type": shot_type or "中景", "angle": angle, "movement": movement, "duration": dur}


def parse_shot_block(block: str, shot_num: tuple, start_line: int) -> dict:
    """解析单个 SHOT 块，返回 shot_data dict。

    shot_num=(场序, 镜序) 用于生成 shot_id。
    start_line 是该块在原文中的起始行号，用于报错定位。
    """
    scene_idx, shot_idx = shot_num
    shot_id = f"{scene_idx:03d}_{shot_idx:02d}"

    # 分离 bullet 区和子标题区
    lines = block.split("\n")
    bullets = {}
    sub_sections = {}  # 子标题 → 内容行列表
    current_sub = None
    current_lines = []

    for line in lines:
        sub_m = re.match(r"^###\s+(.+?)\s*$", line)
        if sub_m:
            if current_sub:
                sub_sections[current_sub] = current_lines
            current_sub = sub_m.group(1).strip()
            current_lines = []
            continue
        if current_sub is not None:
            current_lines.append(line)
        else:
            # bullet 行
            m = re.match(r"^-\s+(.+?)：\s*(.*)$", line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                bullets[key] = val
    if current_sub:
        sub_sections[current_sub] = current_lines

    # 提取子标题内容（去首尾空行）
    def get_sub(name):
        for key in sub_sections:
            if name in key:
                body = "\n".join(sub_sections[key]).strip("\n")
                return body.strip()
        return ""

    script_segment = get_sub("声音")
    # 兼容两种子标题写法：新文档用「首帧提示词」，旧文档用「冻结关键帧提示词」
    keyframe_prompt = get_sub("首帧提示词") or get_sub("冻结关键帧提示词")

    # 解析角色
    characters = parse_characters(bullets.get("角色", ""))

    # 解析道具（格式：玉镯@陈青源手中, 信件@未拆封；「无」等占位词视为没有道具）
    props = []
    for item in bullets.get("道具", "").split(","):
        item = item.strip()
        if not item or item in ("无", "无道具", "无道具。", "none", "None", "-"):
            continue
        if "@" in item:
            pname, pstate = item.split("@", 1)
            props.append({"name": pname.strip(), "state": pstate.strip()})
        else:
            props.append({"name": item, "state": ""})

    # 解析 camera
    camera = parse_camera(
        shot_type=bullets.get("景别", ""),
        placement=bullets.get("机位", ""),
        duration=bullets.get("时长", ""),
    )

    shot_data = {
        "shot_id": shot_id,
        "source": bullets.get("来源", ""),
        "purpose": bullets.get("职责", ""),
        "script_segment": script_segment,
        "action": bullets.get("唯一动作", ""),
        "keyframe_prompt": keyframe_prompt,
        "end_state": bullets.get("终点", ""),
        "characters": characters,
        "props": props,
        "scene": bullets.get("场景", ""),
        "camera": camera,
    }

    # 校验必填字段
    required = ["职责", "唯一动作"]
    missing = [k for k in required if not bullets.get(k)]
    if missing:
        print(f"错误：SHOT-{scene_idx}-{shot_idx}（第 {start_line} 行附近）缺少必填字段：{', '.join(missing)}", file=sys.stderr)
        return None
    if not keyframe_prompt:
        print(f"警告：SHOT-{scene_idx}-{shot_idx} 缺少「冻结关键帧提示词」子标题", file=sys.stderr)

    return shot_data


def parse_storyboard(md_text: str) -> list:
    """解析整个分镜 Markdown，返回 shot_data 列表（按出现顺序）。"""
    shots = []
    # 找所有 SHOT 标题位置
    headers = list(SHOT_HEADER_RE.finditer(md_text))
    if not headers:
        print("错误：未找到任何 ## SHOT-XXX-XX 块", file=sys.stderr)
        return shots

    # 计算每个块的起始行号
    for i, m in enumerate(headers):
        scene_idx = int(m.group(1))
        shot_idx = int(m.group(2))
        start_pos = m.end()
        end_pos = headers[i + 1].start() if i + 1 < len(headers) else len(md_text)
        block = md_text[start_pos:end_pos].strip()
        start_line = md_text[:m.start()].count("\n") + 1
        shot = parse_shot_block(block, (scene_idx, shot_idx), start_line)
        if shot is None:
            continue
        shots.append(shot)
    return shots


# ---------- YAML 写入 ----------

def build_keyframe_full_prompt(keyframe_prompt: str, style: str, aspect_ratio: str, ref_count: int = 0, ref_descriptions: list = None) -> str:
    """拼接首帧图完整提示词，与 gen_video.ensure_keyframe 的拼接逻辑一致。

    用 gen_image.build_prompt 生成结构化提示词（冒号分隔），含参考图引用。
    可直接粘贴到豆包 seedream 网页对话框（参考图手动上传）。
    """
    keyframe_prompt = (keyframe_prompt or "").strip()
    if not keyframe_prompt:
        return ""
    from .gen_image import build_prompt
    return build_prompt(
        keyframe_prompt,
        {"style": style, "aspect_ratio": aspect_ratio},
        "keyframe",
        ref_count=ref_count,
        ref_descriptions=ref_descriptions,
    )


def collect_keyframe_ref_images(project_root: Path, characters: list, scene: str) -> list:
    """收集首帧图参考图路径，与 gen_video.ensure_keyframe 的收集逻辑一致。

    顺序：本镜角色图（保身份，按 characters 顺序）+ 首张场景图（保地理）。
    返回相对项目根的路径列表，供用户照着上传到网页对话框。
    """
    refs = []
    # 角色图（默认形态）
    for char_item in characters or []:
        char_name = char_item.get("name", "") if isinstance(char_item, dict) else str(char_item)
        if not char_name:
            continue
        # 兼容 "角色名:形态名" 写法
        char_name = char_name.split(":")[0] if ":" in char_name else char_name
        char_dir = project_root / "assets" / "characters" / char_name
        if not char_dir.is_dir():
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = char_dir / f"{char_name}{ext}"
            if candidate.exists():
                refs.append(str(candidate.relative_to(project_root)))
                break
    # 场景图（首张）
    if scene:
        scene_dir = project_root / "assets" / "scenes" / scene
        if scene_dir.is_dir():
            imgs = [p for p in scene_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
            if imgs:
                imgs.sort(key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
                refs.append(str(imgs[0].relative_to(project_root)))
    return refs


def write_shot_yaml(filepath: Path, shot_data: dict, shot_id: str, chapter: str, char_map: dict, scene_map: dict, prop_map: dict, config: dict, project_root: Path) -> None:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096

    data = CommentedMap()

    data["shot_id"] = shot_id
    data["chapter"] = chapter
    data.yaml_set_comment_before_after_key("shot_id", before=f"分镜 {shot_id}")

    # 来源（场景 ID + 短引文，追溯用）
    data["source"] = shot_data.get("source", "").strip()
    data.yaml_set_comment_before_after_key("source", before="来源（场景 ID + 短引文）")

    # 镜头职责
    data["purpose"] = shot_data.get("purpose", "").strip()
    data.yaml_set_comment_before_after_key("purpose", before="镜头职责（本镜结束时观众知道了什么变化）")

    # 声音（对白/声音，视频模型用）
    data["script_segment"] = shot_data.get("script_segment", "").strip()
    data.yaml_set_comment_before_after_key("script_segment", before="声音（对白/声音，视频模型消费）")

    # 唯一动作（状态链，视频模型用）
    data["action"] = shot_data.get("action", "").strip()
    data.yaml_set_comment_before_after_key("action", before="唯一动作（起点→终点状态链）")

    # 冻结首帧提示词
    keyframe_prompt = shot_data.get("keyframe_prompt", "").strip()
    data["keyframe_prompt"] = keyframe_prompt
    data.yaml_set_comment_before_after_key("keyframe_prompt", before="冻结首帧提示词（只投影起点，删终点才有的内容）")

    # 首帧图完整提示词（可直接粘贴到豆包 seedream 网页对话框）
    style = config.get("style") or ""
    aspect_ratio = config.get("aspect_ratio") or ""
    # 扫描 assets 构造参考图描述（角色图带角色名+位置，场景图带场景名），与 ensure_keyframe 一致
    mapped_chars = map_characters(shot_data.get("characters") or [], char_map)
    mapped_scene = map_scene(shot_data.get("scene"), scene_map)
    kf_ref_descriptions = []
    for c in mapped_chars:
        c_name = c.get("name", "")
        c_name_clean = c_name.split(":")[0] if ":" in c_name else c_name
        c_dir = project_root / "assets" / "characters" / c_name_clean
        if c_dir.is_dir():
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                if (c_dir / f"{c_name_clean}{ext}").exists():
                    pos = c.get("position", "")
                    desc = f"{c_name}形象"
                    if pos:
                        desc += f"，{pos}"
                    kf_ref_descriptions.append(desc)
                    break
    if mapped_scene:
        s_dir = project_root / "assets" / "scenes" / mapped_scene
        if s_dir.is_dir():
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                if any(p.suffix.lower() == ext for p in s_dir.iterdir()):
                    kf_ref_descriptions.append(f"{mapped_scene}场景")
                    break
    keyframe_full_prompt = build_keyframe_full_prompt(
        keyframe_prompt, style, aspect_ratio,
        ref_count=len(kf_ref_descriptions),
        ref_descriptions=kf_ref_descriptions,
    )
    data["keyframe_full_prompt"] = keyframe_full_prompt
    data.yaml_set_comment_before_after_key("keyframe_full_prompt", before="首帧图完整提示词（可直接粘贴到豆包 seedream 网页对话框，参考图手动上传）")

    # 终点状态
    data["end_state"] = shot_data.get("end_state", "").strip()
    data.yaml_set_comment_before_after_key("end_state", before="终点状态（下一镜起点须与此一致）")

    # 角色引用
    characters = map_characters(shot_data.get("characters") or [], char_map)
    data["characters"] = characters if characters else []
    data.yaml_set_comment_before_after_key("characters", before="角色引用（对应 assets 目录名）")

    # 场景引用
    scene = map_scene(shot_data.get("scene"), scene_map)
    data["scene"] = scene if scene else None
    data.yaml_set_comment_before_after_key("scene", before="场景引用（对应 assets 目录名）")

    # 道具引用
    props = map_props(shot_data.get("props") or [], prop_map)
    data["props"] = props if props else []
    data.yaml_set_comment_before_after_key("props", before="道具引用（对应 assets 目录名，含本镜状态）")

    # 镜头参数
    camera = shot_data.get("camera") or {}
    cam_map = CommentedMap()
    cam_map["shot_type"] = camera.get("shot_type", "中景")
    cam_map["angle"] = camera.get("angle", "平视")
    cam_map["movement"] = camera.get("movement", "固定")
    cam_map["duration"] = camera.get("duration", 15)
    data["camera"] = cam_map
    data.yaml_set_comment_before_after_key("camera", before="镜头参数")

    # 视频提示词（与 gen-video 调 API 时提交的 prompt_text 一致，含 @图片N/@音频N 引用）
    # 模拟"有首帧图"场景：首帧图占 @图片1，角色图从 @图片2 开始
    # 参考图上传顺序：首帧图(keyframe.png) → 角色图 → 场景图 → 道具图 → 角色音色
    shot_for_plan = dict(shot_data)
    shot_for_plan["characters"] = characters
    shot_for_plan["scene"] = scene
    shot_for_plan["props"] = props
    shot_for_plan["camera"] = cam_map
    # 用占位 Path 模拟 keyframe.png 存在，让首帧图编为 @图片1
    keyframe_placeholder = filepath.parent / "keyframe.png"
    try:
        plan = build_prompt_plan(shot_for_plan, project_root, keyframe_image=keyframe_placeholder)
        video_prompt = plan["prompt_text"]
        video_ref_images = [str(p.relative_to(project_root)) for p, _ in plan["ref_images"]]
        video_ref_audios = [str(p.relative_to(project_root)) for p, _ in plan["ref_audios"]]
    except Exception as e:
        print(f"警告：生成视频提示词失败: {e}", file=sys.stderr)
        video_prompt = ""
        video_ref_images = []
        video_ref_audios = []
    data["video_prompt"] = video_prompt
    data.yaml_set_comment_before_after_key("video_prompt", before="视频提示词（与 gen-video 调 API 时提交的 prompt_text 一致，含 @图片N/@音频N 引用）")
    data["video_ref_images"] = video_ref_images
    data.yaml_set_comment_before_after_key("video_ref_images", before="参考图上传顺序（对应 @图片N 编号）")
    data["video_ref_audios"] = video_ref_audios
    data.yaml_set_comment_before_after_key("video_ref_audios", before="参考音频上传顺序（对应 @音频N 编号）")

    # 状态字段
    data["status"] = "pending"
    data["keyframe"] = None
    data["video"] = None

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


# ---------- 映射文件生成 ----------

def scan_existing_characters(project_root: Path) -> list:
    char_dir = project_root / "assets" / "characters"
    if not char_dir.is_dir():
        return []
    return [d.name for d in char_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def scan_existing_scenes(project_root: Path) -> list:
    scene_dir = project_root / "assets" / "scenes"
    if not scene_dir.is_dir():
        return []
    return [d.name for d in scene_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def scan_existing_props(project_root: Path) -> list:
    prop_dir = project_root / "assets" / "props"
    if not prop_dir.is_dir():
        return []
    return [d.name for d in prop_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


def generate_map_files(project_root: Path, chapter: str, shots: list) -> tuple:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 4096

    chapter_dir = project_root / "chapters" / chapter

    char_names = set()
    scene_names = set()
    prop_names = set()
    for shot in shots:
        for c in shot.get("characters") or []:
            char_names.add(_char_name(c))
        if shot.get("scene"):
            scene_names.add(shot["scene"])
        for p in shot.get("props") or []:
            if isinstance(p, str):
                prop_names.add(p)
            else:
                prop_names.add(p.get("name", ""))

    existing_chars = scan_existing_characters(project_root)
    char_map = CommentedMap()
    for name in sorted(char_names):
        if name in existing_chars:
            char_map[name] = name
        else:
            char_map[name] = ""
    char_map_path = chapter_dir / "character_map.yaml"
    with open(char_map_path, "w", encoding="utf-8") as f:
        f.write("# 角色映射 — 剧本角色名 → assets 目录名\n")
        f.write("# 支持多形态：值可填 角色名:形态名（如 小帅:女装）\n")
        f.write("# 未填的请手动补充\n\n")
        yaml.dump(char_map, f)
    print(f"已生成角色映射: {char_map_path}")

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

    # 生成道具映射
    existing_props = scan_existing_props(project_root)
    prop_map = CommentedMap()
    for name in sorted(prop_names):
        if not name:
            continue
        if name in existing_props:
            prop_map[name] = name
        else:
            prop_map[name] = ""
    prop_map_path = chapter_dir / "prop_map.yaml"
    with open(prop_map_path, "w", encoding="utf-8") as f:
        f.write("# 道具映射 — 剧本道具名 → assets 目录名\n")
        f.write("# 未填的请手动补充\n\n")
        yaml.dump(prop_map, f)
    print(f"已生成道具映射: {prop_map_path}")

    return dict(char_map), dict(scene_map), dict(prop_map)


# ---------- 主流程 ----------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort gen-shots", description="从 Markdown 分镜生成 shot YAML")
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

    # 读取 Markdown 分镜文档
    md_path = chapter_dir / "shots.md"
    if not md_path.exists():
        print(f"错误：找不到 {md_path}，请先用 gen-shots 技能写 Markdown 分镜文档", file=sys.stderr)
        return 1

    md_text = md_path.read_text(encoding="utf-8")
    shots = parse_storyboard(md_text)
    if not shots:
        print("错误：未解析到任何分镜，请检查 shots.md 格式（需 ## SHOT-XXX-XX 块）", file=sys.stderr)
        return 1
    print(f"已解析 {len(shots)} 个分镜")

    # 加载 config.yaml
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print(f"错误：config.yaml 不存在: {config_path}", file=sys.stderr)
        return 1
    yaml_cfg = YAML()
    yaml_cfg.allow_unicode = True
    with open(config_path, encoding="utf-8") as f:
        config = yaml_cfg.load(f) or {}

    # 加载映射文件（不存在则自动生成）
    char_map_path = chapter_dir / "character_map.yaml"
    scene_map_path = chapter_dir / "scene_map.yaml"
    prop_map_path = chapter_dir / "prop_map.yaml"
    if not char_map_path.exists() or not scene_map_path.exists() or not prop_map_path.exists():
        char_map, scene_map, prop_map = generate_map_files(project_root, args.chapter, shots)
    else:
        char_map = load_character_map(project_root, args.chapter)
        scene_map = load_scene_map(project_root, args.chapter)
        prop_map = load_prop_map(project_root, args.chapter)
    if char_map:
        print(f"已加载角色映射: {char_map}")
    if scene_map:
        print(f"已加载场景映射: {scene_map}")
    if prop_map:
        print(f"已加载道具映射: {prop_map}")

    # 检查已有文件
    if not args.force:
        existing = list(shots_dir.glob("shot_*/shot.yaml"))
        if existing:
            print(f"错误：{shots_dir} 下已有分镜文件。使用 --force 覆盖。", file=sys.stderr)
            return 1

    # 写入分镜 YAML
    for shot_data in shots:
        shot_id = shot_data["shot_id"]
        shot_dir = shots_dir / f"shot_{shot_id}"
        shot_dir.mkdir(parents=True, exist_ok=True)
        filepath = shot_dir / "shot.yaml"
        write_shot_yaml(filepath, shot_data, shot_id, args.chapter, char_map, scene_map, prop_map, config, project_root)
        print(f"已生成: {filepath}")

    print(f"\n✅ 共生成 {len(shots)} 个分镜")
    print(f"   目录: {shots_dir}")
    print(f"   分镜文档保留: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
