#!/usr/bin/env python3
"""分镜生成视频 — 从 shot YAML 生成视频

用法：
  vcshort gen-video <项目路径> --chapter <章节号> --shot <分镜号> [--with-keyframe]

示例：
  vcshort gen-video /path/to/project --chapter ch01 --shot 001

流程：
  1. 读取 shot YAML（shot_id, source, purpose, script_segment(声音), action, keyframe_prompt, end_state, characters, scene, camera）
  2. 首帧控制：分镜目录下有 keyframe.png 则作为起始画面参考图；--with-keyframe 时按 keyframe_prompt 自动生成
  3. 从 assets 目录扫描角色和场景的图片（约定优于配置）
  4. 将参考图转 base64，作为 reference_image 传给视频生成 API
  5. 轮询任务直到完成，下载视频
  6. 更新 shot YAML 的 video 字段和 status
"""

import argparse
import base64
import sys
import time
import requests
import yaml
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_VIDEO_MODEL = "doubao-seedance-2-0-mini-260615"


def load_config(project_root: Path) -> dict:
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误：config.yaml 不存在", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_shot(shot_path: Path) -> dict:
    if not shot_path.exists():
        print(f"错误：分镜文件不存在: {shot_path}", file=sys.stderr)
        sys.exit(1)
    with open(shot_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_shot(shot_path: Path, shot: dict) -> None:
    """更新 shot YAML 的 video 和 status 字段，保留原有格式和注释。"""
    try:
        from ruamel.yaml import YAML
        yaml_rt = YAML()
        yaml_rt.allow_unicode = True
        yaml_rt.preserve_quotes = True
        yaml_rt.width = 4096
        with open(shot_path, encoding="utf-8") as f:
            data = yaml_rt.load(f)
        data["video"] = shot["video"]
        data["status"] = shot["status"]
        with open(shot_path, "w", encoding="utf-8") as f:
            yaml_rt.dump(data, f)
    except ImportError:
        import yaml
        with open(shot_path, "w", encoding="utf-8") as f:
            yaml.dump(shot, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def image_to_base64(image_path: Path) -> str:
    if not image_path.exists():
        print(f"警告：图片不存在: {image_path}", file=sys.stderr)
        return None
    suffix = image_path.suffix.lower().lstrip(".")
    mime_map = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "bmp": "bmp"}
    mime = mime_map.get(suffix, "png")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


def audio_to_base64(audio_path: Path) -> str:
    """将本地音频文件转为 base64 data URL。"""
    if not audio_path.exists():
        return None
    suffix = audio_path.suffix.lower().lstrip(".")
    mime_map = {"mp3": "mp3", "wav": "wav", "m4a": "mp4", "aac": "aac"}
    mime = mime_map.get(suffix, "mp3")
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:audio/{mime};base64,{b64}"


def find_character_voice(project_root: Path, char_name: str) -> Path | None:
    """从 assets/characters/<char_name>/ 目录查找角色音色文件。"""
    char_dir = project_root / "assets" / "characters" / char_name
    if not char_dir.is_dir():
        return None
    for ext in (".mp3", ".wav", ".m4a", ".aac"):
        candidate = char_dir / f"{char_name}{ext}"
        if candidate.exists():
            return candidate
    return None


def find_character_image(project_root: Path, char_name: str, form_name: str = "默认") -> Path | None:
    """从 assets/characters/<char_name>/ 目录扫描角色图片。
    约定：默认形态为 <char_name>.png，其他形态为 <char_name>-<form>.png
    """
    char_dir = project_root / "assets" / "characters" / char_name
    if not char_dir.is_dir():
        return None
    if form_name and form_name != "默认":
        # 查找 <char_name>-<form_name>.png
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = char_dir / f"{char_name}-{form_name}{ext}"
            if candidate.exists():
                return candidate
    # 默认形态：<char_name>.png
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = char_dir / f"{char_name}{ext}"
        if candidate.exists():
            return candidate
    # 兜底：目录下任意图片
    imgs = [p for p in char_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    return imgs[0] if imgs else None


def find_scene_images(project_root: Path, scene_name: str) -> list:
    """从 assets/scenes/<scene_name>/ 目录扫描所有场景图片，按数字排序。"""
    scene_dir = project_root / "assets" / "scenes" / scene_name
    if not scene_dir.is_dir():
        return []
    imgs = [p for p in scene_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    return sorted(imgs, key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)


def find_prop_image(project_root: Path, prop_name: str) -> Path | None:
    """从 assets/props/<prop_name>/ 目录扫描道具图片。"""
    prop_dir = project_root / "assets" / "props" / prop_name
    if not prop_dir.is_dir():
        return None
    # 优先 <prop_name>.png
    candidate = prop_dir / f"{prop_name}.png"
    if candidate.exists():
        return candidate
    # 兜底：目录下任意图片
    imgs = [p for p in prop_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    return imgs[0] if imgs else None


def build_content(shot: dict, project_root: Path, prev_frame: Path | None = None, keyframe_image: Path | None = None) -> list:
    """构建 API content 数组：文本 + 首帧图/上一镜参考帧 + 角色参考图 + 场景参考图 + 角色参考音频。"""
    content = []

    camera = shot.get("camera") or {}
    script_segment = shot.get("script_segment", "")

    # 从 script_segment 解析出说话人（格式：角色名（动作）：台词）
    import re
    speakers_in_segment = []
    for m in re.finditer(r'^(\S+?)（[^）]+）：', script_segment, flags=re.MULTILINE):
        speaker = m.group(1).strip()
        if speaker and speaker not in speakers_in_segment:
            speakers_in_segment.append(speaker)

    img_index = 1
    keyframe_index = None
    prev_frame_index = None

    # 冻结首帧图（优先）：keyframe.png 即本镜起点画面，已包含与上一镜的连贯性
    if keyframe_image:
        b64 = image_to_base64(keyframe_image)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            keyframe_index = img_index
            img_index += 1

    # 上一镜最后一帧（保持连贯性；有首帧图时不再传，首帧图即本镜起点）
    if prev_frame and not keyframe_image:
        b64 = image_to_base64(prev_frame)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            prev_frame_index = img_index
            img_index += 1

    # 角色参考图（characters 为 dict 列表，含 name/position）
    characters = shot.get("characters") or []
    char_indices = {}
    char_positions = {}
    for char_item in characters:
        char_name = char_item.get("name", "")
        position = char_item.get("position", "")

        char_img = find_character_image(project_root, char_name, "默认")
        if not char_img:
            print(f"警告：未找到角色 {char_name} 的图片（assets/characters/{char_name}/）", file=sys.stderr)
            continue

        b64 = image_to_base64(char_img)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            char_indices[char_name] = img_index
            if position:
                char_positions[char_name] = position
            img_index += 1

    # 场景参考图（支持多张，全部传入增加多样性）
    scene_key = shot.get("scene")
    scene_indices = []
    if scene_key:
        scene_imgs = find_scene_images(project_root, scene_key)
        for scene_img_path in scene_imgs:
            b64 = image_to_base64(scene_img_path)
            if b64:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": b64},
                    "role": "reference_image"
                })
                scene_indices.append(img_index)
                img_index += 1

    # 道具参考图（本镜出现的道具，传图保持视觉一致）
    prop_indices = {}
    for prop_item in shot.get("props") or []:
        prop_name = prop_item.get("name", "") if isinstance(prop_item, dict) else prop_item
        if not prop_name:
            continue
        prop_img = find_prop_image(project_root, prop_name)
        if not prop_img:
            print(f"提示：未找到道具 {prop_name} 的图片（assets/props/{prop_name}/）", file=sys.stderr)
            continue
        b64 = image_to_base64(prop_img)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            prop_indices[prop_name] = img_index
            img_index += 1

    # 角色参考音频（有对白的角色传入音色，让视频用该音色说对白）
    audio_indices = {}
    for speaker in speakers_in_segment:
        char_name = speaker.split(":")[0] if ":" in speaker else speaker
        voice_path = find_character_voice(project_root, char_name)
        if voice_path:
            audio_b64 = audio_to_base64(voice_path)
            if audio_b64:
                content.append({
                    "type": "audio_url",
                    "audio_url": {"url": audio_b64},
                    "role": "reference_audio"
                })
                audio_indices[speaker] = img_index
                img_index += 1
                print(f"  角色 {speaker} 音色: {voice_path.name}")

    # 构建提示词：素材角色指定 + 动作/剧情描述(含对白) + 镜头语言 + 氛围
    prompt_parts = []

    # 1. 素材角色指定（用 @图片N/@音频N 引用，符合 Seedance 官方写法）
    if keyframe_index:
        prompt_parts.append(f"@图片{keyframe_index}作为本镜起始画面")
    if prev_frame_index:
        prompt_parts.append(f"@图片{prev_frame_index}作为上一镜结尾画面，保持连贯")
    for char_key, idx in char_indices.items():
        pos = char_positions.get(char_key)
        if pos:
            prompt_parts.append(f"参考@图片{idx}的{char_key}形象，{pos}")
        else:
            prompt_parts.append(f"参考@图片{idx}的{char_key}形象")
    if scene_indices:
        idx_strs = "、".join(f"@图片{i}" for i in scene_indices)
        prompt_parts.append(f"场景为{idx_strs}")
    for prop_name, idx in prop_indices.items():
        prompt_parts.append(f"参考@图片{idx}的{prop_name}外观")
    for speaker, idx in audio_indices.items():
        prompt_parts.append(f"{speaker}的音色参考@音频{idx}")

    # 1.5 起始画面描述：有上一镜尾图时以图为准，不传 keyframe_prompt（避免文图冲突）；
    # 有首帧图或无任何起始图（文本兜底）时用首帧提示词描述起点
    keyframe_prompt = (shot.get("keyframe_prompt") or "").strip()
    if prev_frame_index:
        prompt_parts.append(f"起始画面参考@图片{prev_frame_index}，从该画面状态开始演")
    elif keyframe_prompt:
        prompt_parts.append(f"起始画面：{keyframe_prompt}")

    # 2. 动作/剧情描述（action 状态链 + script_segment 声音，按时间线叙述）
    action = (shot.get("action") or "").strip()
    if action or script_segment:
        narrative_parts = []
        # 先写动作状态链（唯一动作：起点→终点的可见状态转换）
        if action:
            narrative_parts.append(action)
        # 再写声音（对白/声音），转为自然叙述
        if script_segment:
            seg = script_segment
            # 去掉括号里的纯动作描写行的括号
            seg = re.sub(r'\n（([^）]+)）', r'\n\1', seg)
            # 把 "角色（动作）：台词" 转为 "角色动作，用普通话说"台词""
            def convert_dialogue(m):
                speaker = m.group(1)
                act = m.group(2) or ""
                text = m.group(3) or ""
                parts = []
                if act:
                    parts.append(f"{speaker}{act}")
                if text:
                    parts.append(f'{speaker}用普通话说"{text}"')
                return "，".join(parts)
            seg = re.sub(r'^(\S+?)（([^）]+)）：(.+)$', convert_dialogue, seg, flags=re.MULTILINE)
            seg = seg.replace("\n", "，")
            narrative_parts.append(seg)
        prompt_parts.append("，".join(narrative_parts))

    # 3. 镜头语言（景别 + 运镜 + 角度，归在一起）
    camera_parts = []
    if camera.get("shot_type"):
        camera_parts.append(camera["shot_type"])
    if camera.get("angle"):
        camera_parts.append(camera["angle"])
    if camera.get("movement") and camera["movement"] != "固定":
        camera_parts.append(f"镜头{camera['movement']}")
    if camera_parts:
        prompt_parts.append("，".join(camera_parts))

    # 4. 质量约束
    prompt_parts.append("单个场景中尽量保持镜头固定，减少运镜和镜头切换，画面稳定")
    prompt_parts.append("注意人物与周围环境比例")

    prompt_text = "，".join(prompt_parts)
    content.insert(0, {"type": "text", "text": prompt_text})

    return content


def submit_video_task(content: list, config: dict, ratio: str, duration: int) -> str:
    """提交视频生成任务，返回 task_id。"""
    api_cfg = config.get("api") or {}
    api_key = api_cfg.get("api_key")
    base_url = api_cfg.get("base_url", DEFAULT_BASE_URL)
    model = api_cfg.get("video_model", DEFAULT_VIDEO_MODEL)
    resolution = config.get("resolution", "720p")

    if not api_key:
        print("错误：config.yaml 中未配置 api.api_key", file=sys.stderr)
        sys.exit(1)

    endpoint = f"{base_url}/contents/generations/tasks"
    payload = {
        "model": model,
        "content": content,
        "ratio": ratio,
        "duration": max(duration, 5),
        "resolution": resolution,
        "watermark": False,
        "generate_audio": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    print(f"正在提交视频生成任务...")
    print(f"模型: {model}")
    print(f"比例: {ratio}，时长: {max(duration, 5)}s")

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=(60, 300))
            break
        except requests.exceptions.RequestException as e:
            last_err = e
            print(f"提交请求失败（第 {attempt + 1} 次）：{e}，5 秒后重试...", file=sys.stderr)
            time.sleep(5)
    else:
        print(f"提交失败：重试 3 次仍超时/出错: {last_err}", file=sys.stderr)
        sys.exit(1)
    if resp.status_code != 200:
        print(f"提交失败 ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    result = resp.json()
    task_id = result.get("id")
    if not task_id:
        print(f"API 返回异常: {result}", file=sys.stderr)
        sys.exit(1)

    print(f"任务已提交，task_id: {task_id}")
    return task_id


def poll_task(task_id: str, config: dict, interval: int = 10, max_wait: int = 600) -> str:
    """轮询任务状态，返回视频 URL。"""
    api_cfg = config.get("api") or {}
    api_key = api_cfg.get("api_key")
    base_url = api_cfg.get("base_url", DEFAULT_BASE_URL)
    endpoint = f"{base_url}/contents/generations/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    waited = 0
    while waited < max_wait:
        resp = requests.get(endpoint, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"查询失败 ({resp.status_code}): {resp.text}", file=sys.stderr)
            time.sleep(interval)
            waited += interval
            continue

        result = resp.json()
        status = result.get("status", "")
        print(f"  状态: {status}（已等待 {waited}s）")

        if status == "succeeded":
            content = result.get("content")
            # content 可能是 dict {video_url: "https://..."} 或列表
            if isinstance(content, dict):
                url = content.get("video_url")
                if url:
                    return url
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "video_url":
                        url = item.get("video_url", {}).get("url")
                        if url:
                            return url
            print(f"成功但未找到视频 URL: {result}", file=sys.stderr)
            sys.exit(1)

        if status == "failed":
            error = result.get("error", {})
            print(f"任务失败: {error}", file=sys.stderr)
            sys.exit(1)

        time.sleep(interval)
        waited += interval

    print(f"超时（等待 {max_wait}s）", file=sys.stderr)
    sys.exit(1)


def download_video(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def extract_frames(video_path: Path, shot_dir: Path) -> tuple:
    """从视频提取第一帧和最后一帧，保存到分镜文件夹。
    返回 (first_frame_path, last_frame_path)。
    """
    if cv2 is None:
        print("警告：opencv-python 未安装，跳过帧提取（pip install opencv-python）", file=sys.stderr)
        return None, None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"警告：无法打开视频 {video_path}，跳过帧提取", file=sys.stderr)
        return None, None

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    first_frame_path = shot_dir / "first_frame.png"
    last_frame_path = shot_dir / "last_frame.png"

    # 第一帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, first_frame = cap.read()
    if ret:
        cv2.imwrite(str(first_frame_path), first_frame)
        print(f"已提取第一帧: {first_frame_path}")

    # 最后一帧
    if total_frames > 1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
        ret, last_frame = cap.read()
        if ret:
            cv2.imwrite(str(last_frame_path), last_frame)
            print(f"已提取最后一帧: {last_frame_path}")
    else:
        # 只有一帧，复用第一帧
        if first_frame_path.exists():
            import shutil
            shutil.copy(first_frame_path, last_frame_path)
            print(f"已提取最后一帧（复用第一帧）: {last_frame_path}")

    cap.release()
    return first_frame_path, last_frame_path


def find_prev_last_frame(project_root: Path, chapter: str, shot_num: str) -> Path | None:
    """查找上一个分镜的 last_frame.png，用于保持分镜间连贯性。
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

    prev_frame = project_root / "chapters" / chapter / "shots" / f"shot_{prev_id}" / "last_frame.png"
    if prev_frame.exists():
        return prev_frame
    return None


def ensure_keyframe(shot: dict, project_root: Path, config: dict, shot_dir: Path) -> Path | None:
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

    # 参考图：角色图（保身份）+ 首张场景图（保地理）
    ref_images = []
    for char_item in shot.get("characters") or []:
        char_name = char_item.get("name", "")
        char_name = char_name.split(":")[0] if ":" in char_name else char_name
        img = find_character_image(project_root, char_name, "默认")
        if img:
            ref_images.append(str(img))
    scene_key = shot.get("scene")
    if scene_key:
        scene_imgs = find_scene_images(project_root, scene_key)
        if scene_imgs:
            ref_images.append(str(scene_imgs[0]))

    style = config.get("style")
    aspect = config.get("aspect_ratio")
    parts = [keyframe_prompt, "视频首帧，画面定格瞬间"]
    if style:
        parts.append(f"{style}风格")
    if aspect:
        parts.append(f"{aspect}构图")
    final_prompt = "，".join(parts)

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
    parser = argparse.ArgumentParser(prog="vcshort gen-video", description="从分镜生成视频")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--shot", required=True, help="分镜号（如 001）")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    shot_dir = project_root / "chapters" / args.chapter / "shots" / f"shot_{args.shot}"
    shot_path = shot_dir / "shot.yaml"
    shot = load_shot(shot_path)
    config = load_config(project_root)

    # 检查是否已有视频（在分镜文件夹内）
    video_path = shot_dir / "shot.mp4"
    if video_path.exists():
        print(f"分镜 {args.shot} 已有视频: {video_path}")
        return 0

    # 冻结首帧图：分镜目录下有 keyframe.png 则作为起始画面参考图
    # 首帧图由独立命令 /vc-short:gen-keyframe 生成，本命令不再自动生成
    keyframe_image = shot_dir / "keyframe.png"
    if keyframe_image.exists():
        print(f"使用首帧图: {keyframe_image}")
    else:
        keyframe_image = None
        print("提示：无首帧图，将回退用上一镜尾帧或纯文本提示词（建议先用 /vc-short:gen-keyframe 生成首帧图）", file=sys.stderr)

    # 查找上一镜的最后一帧（保持连贯性；有首帧图时不传，首帧图即本镜起点）
    prev_frame = None
    if not keyframe_image:
        prev_frame = find_prev_last_frame(project_root, args.chapter, args.shot)
        if prev_frame:
            print(f"使用上一镜参考帧: {prev_frame}")

    # 构建 content
    content = build_content(shot, project_root, prev_frame, keyframe_image)
    print(f"参考图数量: {len([c for c in content if c['type'] == 'image_url'])}")

    # 获取比例和时长
    raw_ratio = config.get("aspect_ratio", "9:16")
    ratio = str(raw_ratio) if raw_ratio else "9:16"
    duration = (shot.get("camera") or {}).get("duration", 15)
    # API 支持 5/10/15 秒
    if duration not in (5, 10, 15):
        duration = 15 if duration > 10 else (10 if duration > 5 else 5)

    # 提交任务
    task_id = submit_video_task(content, config, ratio, duration)

    # 轮询等待
    video_url = poll_task(task_id, config)

    # 下载视频
    print(f"视频生成完成，正在下载...")
    download_video(video_url, video_path)
    print(f"已保存: {video_path}")

    # 提取第一帧和最后一帧
    extract_frames(video_path, shot_dir)

    print(f"\n✅ 分镜 {args.shot} 视频生成完成")
    print(f"   视频: {video_path}")
    return 0
