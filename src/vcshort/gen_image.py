#!/usr/bin/env python3
"""图片生成 — 角色 / 服装 / 道具 / 场景

用法：
  vcshort gen-image <项目路径> --type <类型> --name <名称> --prompt <提示词>
  vcshort gen-image <项目路径> --type character --name <角色名> --form <形态名> --prompt <提示词>

类型对应目录：
  character -> assets/characters
  costume  -> assets/costumes
  prop     -> assets/props
  scene    -> assets/scenes

生成后会：
  1. 调用 Volcengine Ark doubao-seedream API 生成图片
  2. 保存到对应目录（约定优于配置，不写 config.yaml）
"""

import argparse
import sys
import time
import requests
import yaml
from pathlib import Path

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedream-4-5-251128"

TYPE_MAP = {
    "character": "characters",
    "costume": "costumes",
    "prop": "props",
    "scene": "scenes",
}


def load_config(project_root: Path) -> dict:
    """加载 config.yaml 为字典（仅用于读取 API 配置和风格配置）。"""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误：config.yaml 不存在", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_prompt(user_prompt: str, style_config: dict, asset_type: str = None) -> str:
    """将用户提示词与项目风格配置拼接。"""
    parts = [user_prompt]
    # 角色默认正面全身照 + 纯色背景，确保脸部可识别且便于图生视频参考
    if asset_type == "character":
        parts.append("正面全身照")
        parts.append("面对镜头")
        parts.append("纯白背景")
    # 场景不出现人物，避免干扰后续图生视频
    if asset_type == "scene":
        parts.append("不要出现人物")
    style = style_config.get("style")
    aspect = style_config.get("aspect_ratio")
    if style:
        parts.append(f"{style}风格")
    if aspect:
        parts.append(f"{aspect}构图")
    return "，".join(parts)


def generate_image(prompt: str, api_config: dict, size: str = "2K", model: str = None, ref_images: list = None) -> str:
    """调用 API 生成图片，返回图片 URL。ref_images 为本地图片路径列表，传入后作为参考图。"""
    api_key = api_config["api_key"]
    base_url = api_config["base_url"]
    if model is None:
        model = api_config.get("image_model", DEFAULT_MODEL)
    endpoint = f"{base_url}/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "watermark": False,
        "response_format": "url",
        "sequential_image_generation": "disabled",
        "stream": False,
    }
    # 参考图：本地图片转 base64 注入 images 字段
    if ref_images:
        import base64
        images_b64 = []
        for img_path in ref_images:
            p = Path(img_path)
            if not p.exists():
                print(f"警告：参考图不存在，跳过: {p}", file=sys.stderr)
                continue
            ext = p.suffix.lstrip(".").lower()
            mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            images_b64.append(f"data:image/{mime};base64,{b64}")
        if images_b64:
            payload["images"] = images_b64
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=300)
            resp.raise_for_status()
            result = resp.json()
            break
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"连接失败，{wait}秒后重试 ({attempt + 1}/{max_retries})...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"网络错误（已重试{max_retries}次）: {e}", file=sys.stderr)
                sys.exit(1)
        except requests.exceptions.HTTPError as e:
            body = resp.text if resp else ""
            print(f"API 错误 ({resp.status_code}): {body}", file=sys.stderr)
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}", file=sys.stderr)
            sys.exit(1)

    if "data" not in result or not result["data"]:
        print(f"API 返回异常: {result}", file=sys.stderr)
        sys.exit(1)

    return result["data"][0]["url"]


def download_image(url: str, dest: Path) -> None:
    """下载图片到本地。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort gen-image", description="生成图片资产")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--type", required=True, choices=TYPE_MAP.keys(), help="资产类型")
    parser.add_argument("--name", required=True, help="资产名称（项目内唯一）")
    parser.add_argument("--prompt", default=None, help="生成提示词（角色类型可省略，读 character.yaml）")
    parser.add_argument("--size", default="2K", help="图片尺寸 (2K/3K/4K)")
    parser.add_argument("--model", default=None, help="模型 ID（默认读 config.yaml）")
    parser.add_argument("--force", action="store_true", help="覆盖同名资产")
    parser.add_argument("--form", default=None, help="角色形态名（仅 type=character 时使用，默认 default）")
    parser.add_argument("--gender", default=None, choices=["male", "female"], help="角色性别（仅 type=character，生成图片后自动生成音色）")
    parser.add_argument("--no-voice", action="store_true", help="不自动生成音色（仅 type=character）")
    parser.add_argument("--ref-image", default=None, help="参考图路径（仅参考风格，形象按提示词走；多张用逗号分隔）")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    asset_dir_name = TYPE_MAP[args.type]
    asset_dir = project_root / "assets" / asset_dir_name

    # 角色类型使用文件夹结构：assets/characters/<角色名>/<角色名>.png 或 <角色名>-<特征>.png
    # 场景类型使用文件夹结构：assets/scenes/<场景名>/<N>.png（数字递增）
    if args.type == "character":
        form_name = args.form or "默认"
        char_dir = asset_dir / args.name
        if form_name == "默认":
            image_filename = f"{args.name}.png"
        else:
            image_filename = f"{args.name}-{form_name}.png"
        image_path = char_dir / image_filename
        image_rel = f"assets/{asset_dir_name}/{args.name}/{image_filename}"

        # 读取 character.yaml 档案（gender / appearance）
        char_yaml_path = char_dir / "character.yaml"
        char_yaml = {}
        if char_yaml_path.exists():
            with open(char_yaml_path, encoding="utf-8") as f:
                char_yaml = yaml.safe_load(f) or {}
        # CLI --gender 覆盖档案里的 gender
        effective_gender = args.gender or char_yaml.get("gender") or ""
        # CLI --prompt 覆盖档案里的 appearance
        effective_prompt = args.prompt or char_yaml.get("appearance") or ""
        if not effective_prompt:
            print("错误：未提供提示词，且 character.yaml 中无 appearance 字段", file=sys.stderr)
            print(f"请编辑 {char_yaml_path} 填入 appearance，或通过 --prompt 指定", file=sys.stderr)
            return 1
    elif args.type == "scene":
        form_name = None
        scene_dir = asset_dir / args.name
        scene_dir.mkdir(parents=True, exist_ok=True)
        # 找下一个可用数字
        existing = sorted(scene_dir.glob("[0-9]*.png"))
        next_num = len(existing) + 1
        image_path = scene_dir / f"{next_num}.png"
        image_rel = f"assets/{asset_dir_name}/{args.name}/{next_num}.png"
    else:
        form_name = None
        image_path = asset_dir / f"{args.name}.png"
        image_rel = f"assets/{asset_dir_name}/{args.name}.png"

    # 加载配置（仅用于 API 和风格配置）
    config = load_config(project_root)

    # 检查图片是否已存在（场景支持多张，不检查）
    if not args.force and args.type != "scene":
        if image_path.exists():
            print(f"错误：图片文件已存在: {image_path}。使用 --force 覆盖。", file=sys.stderr)
            return 1

    # 读取 API 配置和风格配置
    api_cfg = config.get("api") or {}
    api_key = api_cfg.get("api_key")
    if not api_key:
        print("错误：config.yaml 中未配置 api.api_key", file=sys.stderr)
        return 1
    api_config = {"api_key": api_key, "base_url": api_cfg.get("base_url", DEFAULT_BASE_URL), "image_model": api_cfg.get("image_model", DEFAULT_MODEL)}
    style_config = {"style": config.get("style"), "aspect_ratio": config.get("aspect_ratio")}
    model = args.model or api_config.get("image_model", DEFAULT_MODEL)

    # 拼接提示词
    final_prompt = build_prompt(effective_prompt if args.type == "character" else args.prompt, style_config, args.type)

    # 生成图片
    print(f"正在生成 {args.type} 图片: {args.name}")
    print(f"提示词: {final_prompt}")
    print(f"模型: {model}")
    print(f"尺寸: {args.size}")

    # 参考图
    ref_images = None
    if args.ref_image:
        ref_images = [p.strip() for p in args.ref_image.split(",") if p.strip()]
        print(f"参考图: {ref_images}")

    image_url = generate_image(final_prompt, api_config, size=args.size, model=model, ref_images=ref_images)
    print(f"图片生成完成，正在下载...")

    download_image(image_url, image_path)
    print(f"已保存: {image_path}")

    label = f"{args.name}:{form_name}" if form_name else args.name
    print(f"\n✅ {args.type} '{label}' 生成完成")
    print(f"   图片: {image_path}")

    # 角色类型且提供了性别且未禁用音色 → 自动生成音色
    if args.type == "character" and effective_gender and not args.no_voice:
        print(f"\n--- 自动生成角色音色 ---")
        from . import gen_voice
        voice_argv = [str(project_root), "--name", args.name, "--gender", effective_gender]
        if args.force:
            voice_argv.append("--force")
        try:
            gen_voice.main(voice_argv)
        except SystemExit as e:
            if e.code and e.code != 0:
                print(f"⚠️  音色生成失败（不影响图片结果）", file=sys.stderr)

    return 0
