#!/usr/bin/env python3
"""图片修改 — 基于已有图片 + 提示词进行编辑

用法：
  vcshort fix-image <项目路径> --name <资产名> --prompt <修改提示词>
  vcshort fix-image <项目路径> --name <角色名:形态名> --prompt <修改提示词>

流程：
  1. 从 assets 目录查找资产图片（约定优于配置，不读 config.yaml）
  2. 将原图转 base64，拼接提示词（风格 + 修改提示词）
  3. 调用 doubao-seededit API 生成修改后的图片
  4. 备份原图并覆盖
"""

import argparse
import base64
import mimetypes
import sys
import time
import requests
import yaml
from pathlib import Path

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedream-5-0-260128"


def load_config(project_root: Path) -> dict:
    """加载 config.yaml（仅用于 API 配置和风格配置）。"""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误：config.yaml 不存在", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def find_asset_image(project_root: Path, name: str) -> Path:
    """从 assets 目录查找资产图片。
    支持：
      - 角色名 → assets/characters/<角色名>/<角色名>.png
      - 角色名:形态名 → assets/characters/<角色名>/<角色名>-<形态名>.png
      - 场景名 → assets/scenes/<场景名>/ 下最后一张（数字最大）
      - 服装名 → assets/costumes/<服装名>.png
      - 道具名 → assets/props/<道具名>.png
    """
    # 角色多形态：name 格式为 "角色名:形态名"
    if ":" in name:
        char_name, form_name = name.split(":", 1)
        char_dir = project_root / "assets" / "characters" / char_name
        if char_dir.is_dir():
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = char_dir / f"{char_name}-{form_name}{ext}"
                if candidate.exists():
                    return candidate
        print(f"错误：未找到角色形态 '{name}' 的图片（{char_dir}/）", file=sys.stderr)
        sys.exit(1)

    # 普通查找：按目录约定扫描
    # 1. 角色：assets/characters/<name>/<name>.png
    char_dir = project_root / "assets" / "characters" / name
    if char_dir.is_dir():
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = char_dir / f"{name}{ext}"
            if candidate.exists():
                return candidate
        # 兜底：目录下任意图片
        imgs = [p for p in char_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        if imgs:
            return imgs[0]

    # 2. 场景：assets/scenes/<name>/ 下数字最大的图片
    scene_dir = project_root / "assets" / "scenes" / name
    if scene_dir.is_dir():
        imgs = [p for p in scene_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        if imgs:
            imgs_sorted = sorted(imgs, key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
            return imgs_sorted[-1]

    # 3. 服装：assets/costumes/<name>.png
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = project_root / "assets" / "costumes" / f"{name}{ext}"
        if candidate.exists():
            return candidate

    # 4. 道具：assets/props/<name>.png
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = project_root / "assets" / "props" / f"{name}{ext}"
        if candidate.exists():
            return candidate

    print(f"错误：未找到资产 '{name}' 的图片（在 assets/ 目录下）", file=sys.stderr)
    sys.exit(1)


def encode_image_to_base64(image_path: Path) -> str:
    """将本地图片转为 data URL。"""
    if not image_path.exists():
        print(f"错误：图片文件不存在: {image_path}", file=sys.stderr)
        sys.exit(1)
    mime, _ = mimetypes.guess_type(str(image_path))
    if not mime:
        mime = "image/png"
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def edit_image(image_data_url: str, prompt: str, api_config: dict) -> str:
    """调用 seedream API 编辑图片，返回新图片 URL。"""
    api_key = api_config["api_key"]
    base_url = api_config["base_url"]
    model = api_config.get("image_model", DEFAULT_MODEL)
    endpoint = f"{base_url}/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "image": image_data_url,
        "response_format": "url",
        "size": "2K",
        "watermark": False,
    }
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
        except requests.exceptions.HTTPError:
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
    parser = argparse.ArgumentParser(prog="vcshort fix-image", description="修改图片资产")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--name", required=True, help="要修改的资产名称（角色名、角色名:形态名、场景名等）")
    parser.add_argument("--prompt", required=True, help="修改提示词")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    # 加载配置（仅用于 API 和风格）
    config = load_config(project_root)

    # 从 assets 目录查找图片
    image_path = find_asset_image(project_root, args.name)

    print(f"找到资产: {args.name}")
    print(f"  图片: {image_path}")

    # 读取 API 配置和风格配置
    api_cfg = config.get("api") or {}
    api_key = api_cfg.get("api_key")
    if not api_key:
        print("错误：config.yaml 中未配置 api.api_key", file=sys.stderr)
        return 1
    api_config = {"api_key": api_key, "base_url": api_cfg.get("base_url", DEFAULT_BASE_URL), "image_model": api_cfg.get("image_model", DEFAULT_MODEL)}

    style = config.get("style")
    aspect = config.get("aspect_ratio")

    # 拼接提示词：风格 + 修改提示词
    parts = []
    if style:
        parts.append(f"{style}风格")
    if aspect:
        parts.append(f"{aspect}构图")
    parts.append(args.prompt)
    final_prompt = "，".join(parts)

    # 编码原图
    image_data_url = encode_image_to_base64(image_path)

    # 调用编辑 API
    print(f"\n正在修改图片: {args.name}")
    print(f"提示词: {final_prompt}")
    print(f"模型: {api_config['image_model']}")

    new_url = edit_image(image_data_url, final_prompt, api_config)
    print("图片修改完成，正在下载...")

    # 备份原图并覆盖
    backup_path = image_path.with_suffix(image_path.suffix + ".bak")
    if image_path.exists():
        image_path.rename(backup_path)

    download_image(new_url, image_path)
    print(f"已保存: {image_path}")
    print(f"原图备份: {backup_path}")

    print(f"\n✅ '{args.name}' 修改完成")
    print(f"   图片: {image_path}")
    return 0
