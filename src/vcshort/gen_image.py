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
  face     -> assets/characters/抽卡（面部抽卡：8格肖像筛选）

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
    "face": "characters/抽卡",
    "extra": "characters/群演",
}


def load_config(project_root: Path) -> dict:
    """加载 config.yaml 为字典（仅用于读取 API 配置和风格配置）。"""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误：config.yaml 不存在", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_prompt(user_prompt: str, style_config: dict, asset_type: str = None, ref_count: int = None, ref_descriptions: list = None, shot_type: str = None, keep_identity: bool = False, designs: bool = False, face_costume: bool = False, cells: int = 8) -> str:
    """将用户提示词与项目风格配置拼接为结构化提示词（冒号分隔，换行组织）。

    ref_count > 0 时加参考图引用（seedream 用"图N"引用，对应 image 字段顺序）。
    ref_descriptions 为每个参考图的描述（如 ["角色形象", "场景"]），不传则默认"整体画风与服饰风格"。
    角色类型默认 ref_count=1（用1张已有角色图保画风一致）；其他类型默认 0。
    """
    if ref_count is None:
        ref_count = 1 if asset_type == "character" else 0
    lines = []
    # 参考图只标注对应主体，位置等构图信息统一放在“画面”中，避免两处描述互相干扰
    if ref_count > 0:
        if ref_descriptions:
            image_refs = []
            scene_refs = []
            other_refs = []
            for i, desc in zip(range(1, ref_count + 1), ref_descriptions):
                subject = desc.partition("，")[0]
                if subject.endswith("形象"):
                    image_refs.append(f"{subject[:-2]}@图{i}")
                elif subject.endswith("场景"):
                    scene_refs.append(f"{subject[:-2]}@图{i}")
                else:
                    other_refs.append(f"{subject}@图{i}")
            if image_refs:
                lines.append(f"形象参考：{'，'.join(image_refs)}")
            if scene_refs:
                lines.append(f"场景参考：{'，'.join(scene_refs)}")
            if other_refs:
                lines.append(f"参考：{'，'.join(other_refs)}")
        else:
            lines.append("形象参考：" + "，".join(f"整体画风与服饰风格@图{i}" for i in range(1, ref_count + 1)))
        # 约束：仅角色生成时加。默认参考图只保画风和服饰，面部按 appearance 大幅调整；
        # 出角色形态图（--form）时相反：同一角色，脸和发型严格一致，只换服装；
        # 脸+服装拼接模式（--face-image/--costume-image）：图1保脸、图2保服装
        if asset_type == "character":
            if face_costume:
                lines.append("约束：参考图1的面部和图2的服装生成角色图，要求高颜值，美观")
            elif keep_identity:
                lines.append("约束：同一角色的不同形态，面部五官、发型、体型严格与参考图一致不得偏离；仅服装按提示词更换")
            else:
                lines.append("约束：面部细节要大幅调整，眼睛大小、双眼间距、嘴唇弧度、发型、眉毛角度、脸型都要有明显变化；服装样式需要大幅调整")
    # 外貌/主体描述
    if asset_type == "keyframe":
        lines.append(f"画面：{user_prompt}")
        if shot_type:
            shot_type_descriptions = {
                "近景": "近景，人物胸部以上，突出面部和表情",
                "中景": "中景，人物腰部或膝盖以上，看清站位、手部动作和部分环境",
                "远景": "远景，人物全身可见，交代2-3人的位置关系和空间环境",
                "全景": "全景，人物全身可见，交代多人关系和完整空间环境",
            }
            lines.append(f"景别：{shot_type_descriptions.get(shot_type, shot_type)}")
        lines.append("用途：作为图生视频的起始画面")
        # 约束：首帧图人物形象必须严格与参考图一致，保身份
        if ref_count > 0:
            lines.append("约束：画面只出现画面描述中的人物，不新增其他人；人物形象严格与参考图一致，五官、发型、服饰、体型不得偏离")
    else:
        # 脸+服装拼接模式下不写外貌——形象完全由两张参考图决定
        if not face_costume:
            lines.append(f"外貌：{user_prompt}")
    # 服装图：8格展示图，无人物，整张即资产
    # 默认选色图（同款式异色）；--designs 为选型图（同风格异款）
    if asset_type == "costume":
        if designs:
            lines.append("构图：8款不同的服装设计展示图，4列×2行网格排列，每格是一套完整服装的平铺/人台展示，格间留白分明")
            lines.append("多样性：8款服装的款式、剪裁、结构、细节各不相同，有明显设计差异；保持同一风格主题和档次")
        else:
            lines.append("构图：8套服装展示图，4列×2行网格排列，每格是一套完整服装的平铺/人台展示，格间留白分明")
            lines.append("一致性：8套服装的款式、版型、剪裁、细节、面料完全一致，仅配色不同")
        lines.append("背景：统一纯色简洁背景，不遮挡服装细节")
        lines.append("全身：每格服装从头到脚完整展示，上衣、下装、鞋靴齐全入画，不裁切、不只显示半身")
        lines.append("要求：不要出现人物、模特")
    # 面部抽卡/群演：N格不同人物肖像/全身像，用于筛选
    grid_desc = "4列×1行" if cells == 4 else "4列×2行"
    if asset_type == "face":
        lines.append(f"构图：{cells}个不同人物的面部特写头像，{grid_desc}网格排列，每格是一个完整的正面肖像，格间留白分明")
        lines.append(f"多样性：{cells}个不同的虚拟人物个体，五官有明显差异，眼睛、鼻子、嘴巴、眉毛、发型各不相同；年龄、性别严格符合外貌描述")
        lines.append("背景：统一纯色简洁背景，不遮挡面部")
        lines.append("画风：CG风格，影视级角色建模，五官精致漂亮、皮肤材质细腻、发丝分明，非真人照片、非写实摄影")
    # 群演抽卡：N格不同人物全身像，可配 --ref-image 锁服装款式
    if asset_type == "extra":
        lines.append(f"构图：{cells}个不同人物的全身立像，{grid_desc}网格排列，格间留白分明")
        lines.append("全身：每格人物从头到脚完整入画，双脚和鞋子可见，头顶与脚下保留适当留白，不要只画半身胸像")
        lines.append(f"多样性：{cells}个不同的虚拟人物个体，五官有明显差异，眼睛、鼻子、嘴巴、眉毛、发型各不相同；年龄、性别严格符合外貌描述")
        if ref_count:
            lines.append(f"服装：{cells}个人物的服装款式、配色、结构严格与图1一致不得偏离")
        lines.append("背景：统一纯色简洁背景")
        lines.append("比例：人物头身比符合年龄段（成年人约1:7，儿童约1:4.5，不要Q版化）")
        lines.append("画风：CG风格，影视级角色建模，五官精致漂亮、皮肤材质细腻、发丝分明，非真人照片、非写实摄影")
    # 角色四视图设定图（正面/侧面/背面全身 + 面部特写）+ 纯白背景，
    # 确保各角度身份一致，便于图生视频在不同景别/机位时保持角色一致
    if asset_type == "character":
        lines.append("构图：并排四张，第一张是正面全身像，第二张是侧面全身像，第三张是背面全身像，第四张是面部特写")
        lines.append("一致性：同一角色，服装发型完全一致")
        lines.append("背景：纯白背景")
        lines.append("全身像要求：人物从头到脚完整入画，双脚和鞋子可见，头顶与脚下保留适当留白")
        lines.append("比例：人物头身比符合年龄段（成年人约1:7，儿童约1:4.5，不要Q版化）")
        # 防写实：脸部过度写实会被视频 API 审核判定为真人（InputImageSensitiveContentDetected）
        lines.append("画风：最终幻想式3D CG风格，影视级角色建模，五官精致华丽、皮肤材质细腻、发丝分明，服装有精美细节，非真人照片、非写实摄影")
    # 场景4景别设定图（2×2网格），按景别梯度覆盖远/全/中/近便于分镜取景；不出现人物，避免干扰后续图生视频
    if asset_type == "scene":
        lines.append("构图：同一场景的4个画面按景别梯度取景，2列×2行网格排列，格间留白分明：远景俯瞰交代场地全貌、全景平视主要区域、中景聚焦核心功能区域、近景特写局部细节")
        lines.append("一致性：4个画面是同一场景的不同景别取景，环境、陈设、光线氛围一致")
        lines.append("要求：不要出现人物和道具")
    style = style_config.get("style")
    aspect = style_config.get("aspect_ratio")
    if style:
        lines.append(f"风格：{style}风格")
    if aspect:
        lines.append(f"比例：{aspect}构图")
    return "\n".join(lines)


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
    # 参考图：本地图片转 base64 注入 image 字段（seedream 多图融合用 image，不是 images）
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
            payload["image"] = images_b64
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
    parser.add_argument("--designs", action="store_true", help="服装选型图：8款同风格不同设计的服装（仅 type=costume，默认是同款式异色）")
    parser.add_argument("--age", default=None, help="年龄段（仅 type=face，如 青年/中年/老年/儿童）")
    parser.add_argument("--hair", default=None, help="发型整体偏向（仅 type=face，八格发型各异，此项为倾向，如 短发/卷发）")
    parser.add_argument("--cells", type=int, default=8, choices=[4, 8], help="格图格数（仅 type=face/extra，默认8格4×2；4格为4×1横排）")
    parser.add_argument("--face-image", default=None, help="面部参考图路径（仅 type=character，需与 --costume-image 同用：图1保脸）")
    parser.add_argument("--costume-image", default=None, help="服装参考图路径（仅 type=character，需与 --face-image 同用：图2保服装）")
    args = parser.parse_args(argv)

    if args.designs and args.type != "costume":
        print("错误：--designs 仅支持 --type costume", file=sys.stderr)
        return 1

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
        if not effective_prompt and not (args.face_image and args.costume_image):
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
    elif args.type == "prop":
        form_name = None
        prop_dir = asset_dir / args.name
        prop_dir.mkdir(parents=True, exist_ok=True)
        image_path = prop_dir / f"{args.name}.png"
        image_rel = f"assets/{asset_dir_name}/{args.name}/{args.name}.png"
    else:
        form_name = None
        asset_dir.mkdir(parents=True, exist_ok=True)
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

    # 参考图
    ref_images = None
    ref_descriptions = None
    face_costume = False
    if args.face_image or args.costume_image:
        if args.type != "character" or not (args.face_image and args.costume_image):
            print("错误：--face-image 与 --costume-image 需同时提供，且仅支持 --type character", file=sys.stderr)
            return 1
        if args.ref_image:
            print("错误：--face-image/--costume-image 不可与 --ref-image 同用", file=sys.stderr)
            return 1
        ref_images = [args.face_image, args.costume_image]
        ref_descriptions = ["面部五官与发型", "服装"]
        face_costume = True
        print(f"参考图: {ref_images}")
    elif args.ref_image:
        ref_images = [p.strip() for p in args.ref_image.split(",") if p.strip()]
        if args.type == "extra":
            ref_descriptions = ["服装"]
        print(f"参考图: {ref_images}")

    # 面部抽卡/群演：年龄段 + 性别 + 发型 + 补充描述拼成外貌提示词
    if args.type in ("face", "extra"):
        gender_zh = {"male": "男性", "female": "女性"}.get(args.gender, "")
        hair_desc = f"发型偏向{args.hair}" if args.hair else None
        face_parts = [p for p in (args.age, gender_zh, hair_desc, args.prompt) if p]
        if not face_parts:
            print(f"错误：--type {args.type} 需要 --age/--hair/--gender/--prompt 至少一项", file=sys.stderr)
            return 1
        face_prompt = "，".join(face_parts)

    # 拼接提示词（有参考图时加"参考图N"引用，对应 image 字段顺序）
    ref_count = len(ref_images) if ref_images else 0
    if args.type == "character":
        prompt_text = effective_prompt
    elif args.type in ("face", "extra"):
        prompt_text = face_prompt
    else:
        prompt_text = args.prompt
    final_prompt = build_prompt(
        prompt_text,
        style_config,
        args.type,
        ref_count=ref_count,
        ref_descriptions=ref_descriptions,
        keep_identity=(args.type == "character" and bool(args.form)),
        designs=args.designs,
        face_costume=face_costume,
        cells=args.cells,
    )

    # 生成图片
    print(f"正在生成 {args.type} 图片: {args.name}")
    print(f"提示词: {final_prompt}")
    print(f"模型: {model}")
    print(f"尺寸: {args.size}")

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
