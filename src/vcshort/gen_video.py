#!/usr/bin/env python3
"""分镜生成视频 — 从 shot YAML 生成视频

用法：
  vcshort gen-video <项目路径> --chapter <章节号> --shot <分镜号>

示例：
  vcshort gen-video /path/to/project --chapter ch01 --shot 001

流程：
  1. 读取 shot YAML（shot_id, visual_prompt, characters, scene, camera）
  2. 从 assets 目录扫描角色和场景的图片（约定优于配置）
  3. 将本地图片转 base64，作为 reference_image 传给视频生成 API
  4. 轮询任务直到完成，下载视频
  5. 更新 shot YAML 的 video 字段和 status
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


def build_content(shot: dict, project_root: Path, prev_frame: Path | None = None) -> list:
    """构建 API content 数组：文本 + 上一镜参考帧 + 角色参考图 + 场景参考图。"""
    content = []

    # 文本提示词
    visual_prompt = shot.get("visual_prompt", "")
    camera = shot.get("camera") or {}
    dialogue = shot.get("dialogue") or []
    prompt_parts = [visual_prompt]
    # 加入对白内容
    for d in dialogue:
        speaker = d.get("speaker", "")
        text = d.get("text", "")
        emotion = d.get("emotion", "")
        if text:
            line = f"{speaker}说「{text}」"
            if emotion:
                line += f"（{emotion}）"
            prompt_parts.append(line)
    if camera.get("movement") and camera["movement"] != "固定":
        prompt_parts.append(f"镜头{camera['movement']}")
    if camera.get("shot_type"):
        prompt_parts.append(camera["shot_type"])
    prompt_parts.append("注意人物与周围环境比例")
    prompt_text = "，".join(prompt_parts)
    content.append({"type": "text", "text": prompt_text})

    img_index = 1
    prev_frame_index = None

    # 上一镜最后一帧（保持连贯性）
    if prev_frame:
        b64 = image_to_base64(prev_frame)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            prev_frame_index = img_index
            img_index += 1

    # 角色参考图（支持 "角色名" 或 "角色名:形态名"）
    characters = shot.get("characters") or []
    char_indices = {}
    for char_ref in characters:
        if ":" in char_ref:
            char_name, form_name = char_ref.split(":", 1)
        else:
            char_name, form_name = char_ref, "默认"

        char_img = find_character_image(project_root, char_name, form_name)
        if not char_img:
            print(f"警告：未找到角色 {char_ref} 的图片（assets/characters/{char_name}/）", file=sys.stderr)
            continue

        b64 = image_to_base64(char_img)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64},
                "role": "reference_image"
            })
            char_indices[char_ref] = img_index
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

    # 重写 prompt，用 [图N] 引用
    if prev_frame_index or char_indices or scene_indices:
        ref_parts = []
        if prev_frame_index:
            ref_parts.append(f"[图{prev_frame_index}]为上一镜结尾画面，保持连贯")
        for char_key, idx in char_indices.items():
            ref_parts.append(f"[图{idx}]为角色{char_key}")
        if scene_indices:
            idx_strs = "、".join(f"[图{i}]" for i in scene_indices)
            ref_parts.append(f"{idx_strs}为场景")
        ref_text = "，".join(ref_parts)
        content[0]["text"] = f"{ref_text}。{prompt_text}"

    return content


def submit_video_task(content: list, config: dict, ratio: str, duration: int) -> str:
    """提交视频生成任务，返回 task_id。"""
    api_cfg = config.get("api") or {}
    api_key = api_cfg.get("api_key")
    base_url = api_cfg.get("base_url", DEFAULT_BASE_URL)
    model = api_cfg.get("video_model", DEFAULT_VIDEO_MODEL)

    if not api_key:
        print("错误：config.yaml 中未配置 api.api_key", file=sys.stderr)
        sys.exit(1)

    endpoint = f"{base_url}/contents/generations/tasks"
    payload = {
        "model": model,
        "content": content,
        "ratio": ratio,
        "duration": max(duration, 5),
        "resolution": "720p",
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

    resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
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
    """查找上一个分镜的 last_frame.png，用于保持分镜间连贯性。"""
    prev_num = int(shot_num) - 1
    if prev_num < 1:
        return None
    prev_shot_id = f"{prev_num:03d}"
    prev_frame = project_root / "chapters" / chapter / "shots" / f"shot_{prev_shot_id}" / "last_frame.png"
    if prev_frame.exists():
        return prev_frame
    return None


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

    # 查找上一镜的最后一帧（保持连贯性）
    prev_frame = find_prev_last_frame(project_root, args.chapter, args.shot)
    if prev_frame:
        print(f"使用上一镜参考帧: {prev_frame}")

    # 构建 content
    content = build_content(shot, project_root, prev_frame)
    print(f"参考图数量: {len([c for c in content if c['type'] == 'image_url'])}")

    # 获取比例和时长
    raw_ratio = config.get("aspect_ratio", "9:16")
    ratio = str(raw_ratio) if raw_ratio else "9:16"
    duration = (shot.get("camera") or {}).get("duration", 10)
    # API 只支持 5 或 10 秒
    if duration not in (5, 10):
        duration = 10 if duration > 5 else 5

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
