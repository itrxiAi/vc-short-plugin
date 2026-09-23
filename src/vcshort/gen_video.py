#!/usr/bin/env python3
"""分镜生成视频 — 从 shot YAML 生成视频

用法：
  vcshort gen-video <项目路径> --chapter <章节号> --shot <分镜号> [--with-keyframe]

示例：
  vcshort gen-video /path/to/project --chapter ch01 --shot 001

流程：
  1. 读取 shot YAML（shot_id, source, purpose, script_segment(声音), action, performance, keyframe_prompt, characters, scene, camera）
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
    群演特殊处理：从 assets/群演/ 目录查找 群演N.png
    """
    # 群演特殊处理：assets/characters/群演/群演N.png
    if char_name.startswith("群演"):
        extra_dir = project_root / "assets" / "characters" / "群演"
        if extra_dir.is_dir():
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = extra_dir / f"{char_name}{ext}"
                if candidate.exists():
                    return candidate
        return None
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


def build_prompt_plan(shot: dict, project_root: Path, keyframe_image: Path | None = None, allow_missing_keyframe: bool = False) -> dict:
    """扫描素材、编索引、拼提示词，不读 base64（dry-run 安全）。

    返回 {
        "prompt_text": str,           # 完整提示词，与 API 提交时一致
        "ref_images": [(path, idx)],  # 参考图路径 + @图片N 索引
        "ref_audios": [(path, idx)],   # 参考音频路径 + @音频N 索引
    }
    """
    camera = shot.get("camera") or {}
    script_segment = shot.get("script_segment", "")

    # 从 script_segment 解析出说话人（格式：角色名（动作）：台词）
    import re
    speakers_in_segment = []
    for m in re.finditer(r'^(\S+?)(?:（[^）]+）)?：', script_segment, flags=re.MULTILINE):
        speaker = m.group(1).strip()
        if speaker and speaker not in speakers_in_segment:
            speakers_in_segment.append(speaker)

    img_index = 1
    keyframe_index = None
    ref_images = []  # [(path, idx)]
    ref_audios = []   # [(path, idx)]

    # 冻结首帧图（优先）：keyframe.png 即本镜起点画面，已包含与上一镜的连贯性
    if keyframe_image and (keyframe_image.exists() or allow_missing_keyframe):
        keyframe_index = img_index
        ref_images.append((keyframe_image, img_index))
        img_index += 1

    # 角色参考图（characters 为 dict 列表，含 name/position）
    # 注：position 只用于首帧图生成，不进 video_prompt
    characters = shot.get("characters") or []
    char_indices = {}
    for char_item in characters:
        char_name = char_item.get("name", "")

        char_img = find_character_image(project_root, char_name, "默认")
        if not char_img:
            print(f"警告：未找到角色 {char_name} 的图片（assets/characters/{char_name}/）", file=sys.stderr)
            continue

        char_indices[char_name] = img_index
        ref_images.append((char_img, img_index))
        img_index += 1

    # 场景参考图（支持多张，全部传入增加多样性）
    scene_key = shot.get("scene")
    scene_indices = []
    if scene_key:
        scene_imgs = find_scene_images(project_root, scene_key)
        for scene_img_path in scene_imgs:
            scene_indices.append(img_index)
            ref_images.append((scene_img_path, img_index))
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
        prop_indices[prop_name] = img_index
        ref_images.append((prop_img, img_index))
        img_index += 1

    # 角色参考音频（有对白的角色传入音色，让视频用该音色说对白）
    audio_indices = {}
    for speaker in speakers_in_segment:
        char_name = speaker.split(":")[0] if ":" in speaker else speaker
        voice_path = find_character_voice(project_root, char_name)
        if voice_path:
            audio_indices[speaker] = img_index
            ref_audios.append((voice_path, img_index))
            img_index += 1
            print(f"  角色 {speaker} 音色: {voice_path.name}")

    # 构建提示词：结构化 key：value 换行格式
    # 参考 / 起始画面 / 动作 / 对白 / 镜头 / 约束
    sections = []  # [(key, value)]

    # 1. 参考（素材角色指定，用 @图片N/@音频N 引用，符合 Seedance 官方写法）
    ref_parts = []
    if keyframe_index:
        ref_parts.append(f"@图片{keyframe_index}作为本镜起始画面")
    for char_key, idx in char_indices.items():
        ref_parts.append(f"参考@图片{idx}的{char_key}形象")
    if scene_indices:
        idx_strs = "、".join(f"@图片{i}" for i in scene_indices)
        ref_parts.append(f"场景为{idx_strs}")
    for prop_name, idx in prop_indices.items():
        ref_parts.append(f"参考@图片{idx}的{prop_name}外观")
    for speaker, idx in audio_indices.items():
        ref_parts.append(f"{speaker}的音色参考@音频{idx}")
    if ref_parts:
        sections.append(("参考", "，".join(ref_parts)))

    # 2. 起始画面：有首帧图时以图片为准，不再重复拼接文字字段；
    #    没有首帧图时才用 keyframe_prompt 作为文字兜底
    keyframe_prompt = (shot.get("keyframe_prompt") or "").strip()
    if not keyframe_index and keyframe_prompt:
        sections.append(("起始画面", keyframe_prompt))

    # 3. 表演（动作与对白的时序叙述，一段给模型）
    performance = (shot.get("performance") or "").strip()
    if performance:
        sections.append(("表演", performance))

    # 5. 镜头（景别 + 运镜 + 角度）
    camera_parts = []
    if camera.get("shot_type"):
        camera_parts.append(camera["shot_type"])
    if camera.get("angle"):
        camera_parts.append(camera["angle"])
    if camera.get("movement"):
        mv = camera["movement"]
        camera_parts.append("固定镜头" if mv == "固定" else f"镜头{mv}")
    if camera_parts:
        sections.append(("镜头", "，".join(camera_parts)))

    # 6. 约束（质量约束）
    sections.append(("约束", "画面稳定，注意人物与周围环境比例，严禁将一个角色面部替换成另一个人的面部"))

    prompt_text = "\n".join(f"{k}：{v}" for k, v in sections)

    return {
        "prompt_text": prompt_text,
        "ref_images": ref_images,
        "ref_audios": ref_audios,
    }


def build_content(shot: dict, project_root: Path, keyframe_image: Path | None = None) -> list:
    """构建 API content 数组：文本 + 首帧图 + 角色参考图 + 场景参考图 + 角色参考音频。"""
    plan = build_prompt_plan(shot, project_root, keyframe_image)
    content = []

    # 参考图（按 plan 顺序读 base64）
    for img_path, idx in plan["ref_images"]:
        b64 = image_to_base64(img_path)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })

    # 参考音频
    for audio_path, idx in plan["ref_audios"]:
        audio_b64 = audio_to_base64(audio_path)
        if audio_b64:
            content.append({
                "type": "audio_url",
                "audio_url": {"url": audio_b64},
                "role": "reference_audio"
            })

    # 文本提示词放最前
    content.insert(0, {"type": "text", "text": plan["prompt_text"]})

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
        print("提示：无首帧图，将用纯文本提示词（建议先用 /vc-short:gen-keyframe 生成首帧图）", file=sys.stderr)

    # 构建 content
    content = build_content(shot, project_root, keyframe_image)
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
