#!/usr/bin/env python3
"""vcshort CLI 主入口 — AI 短视频制作命令行工具。

用法：
    vcshort <command> [args...]

子命令：
    init              初始化项目
    config-list       列出已有资产
    extract           提取资产并匹配
    gen-image         生成图片资产
    gen-voice         生成角色音色
    fix-image         修改图片资产
    reshape-image     身材重塑（瘦胖/高矮/腿比/头比，纯几何变形）
    gen-shots         拆分分镜
    gen-keyframe      生成分镜首帧图
    gen-video         生成分镜视频
    compose-chapter   合成章节视频
"""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vcshort",
        description="AI 短视频制作 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init <项目名>
    p_init = sub.add_parser("init", help="初始化项目")
    p_init.add_argument("name", help="项目名")

    # config-list <项目路径> list
    p_cfg = sub.add_parser("config-list", help="列出已有资产")
    p_cfg.add_argument("project", help="项目路径")
    p_cfg.add_argument("subcommand", nargs="?", default="list", help="子命令（默认 list）")

    # extract <项目路径> --chapter <章节号> [--confirm]
    p_extract = sub.add_parser("extract", help="提取资产并匹配")
    p_extract.add_argument("project", help="项目路径")
    p_extract.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_extract.add_argument("--confirm", action="store_true", help="用户确认后生成 map 文件")

    # gen-image <项目路径> --type --name --prompt [--form] [--size] [--model] [--force] [--gender] [--no-voice]
    p_gen_img = sub.add_parser("gen-image", help="生成图片资产")
    p_gen_img.add_argument("project", help="项目路径")
    p_gen_img.add_argument("--type", required=True, choices=["character", "costume", "prop", "scene", "face", "extra"], help="资产类型")
    p_gen_img.add_argument("--name", required=True, help="资产名称")
    p_gen_img.add_argument("--prompt", default=None, help="生成提示词（角色类型可省略，读 character.yaml）")
    p_gen_img.add_argument("--size", default="2K", help="图片尺寸 (2K/3K/4K)")
    p_gen_img.add_argument("--model", default=None, help="模型 ID（默认读 config.yaml）")
    p_gen_img.add_argument("--force", action="store_true", help="覆盖同名资产")
    p_gen_img.add_argument("--form", default=None, help="角色形态名（仅 type=character）")
    p_gen_img.add_argument("--gender", default=None, choices=["male", "female"], help="角色性别（仅 type=character，生成图片后自动生成音色）")
    p_gen_img.add_argument("--no-voice", action="store_true", help="不自动生成音色（仅 type=character）")
    p_gen_img.add_argument("--ref-image", default=None, help="参考图路径（仅参考风格，形象按提示词走；多张用逗号分隔）")
    p_gen_img.add_argument("--designs", action="store_true", help="服装选型图：8款同风格不同设计（仅 type=costume）")
    p_gen_img.add_argument("--age", default=None, help="年龄段（仅 type=face/extra）")
    p_gen_img.add_argument("--hair", default=None, help="发型整体偏向（仅 type=face/extra，八格各异）")
    p_gen_img.add_argument("--cells", type=int, default=8, choices=[4, 8], help="格图格数（仅 type=face/extra，默认8，4为四格横排）")
    p_gen_img.add_argument("--face-image", default=None, help="面部参考图（仅 type=character，与 --costume-image 同用）")
    p_gen_img.add_argument("--costume-image", default=None, help="服装参考图（仅 type=character，与 --face-image 同用）")

    # gen-voice <项目路径> --name --gender [--voice] [--instruction] [--emotion] [--emotion-scale] [--force]
    p_gen_voice = sub.add_parser("gen-voice", help="生成角色音色")
    p_gen_voice.add_argument("project", help="项目路径")
    p_gen_voice.add_argument("--name", required=True, help="角色名")
    p_gen_voice.add_argument("--gender", required=True, choices=["male", "female"], help="角色性别")
    p_gen_voice.add_argument("--voice", help="指定音色 ID（如 zh_male_qingcang_uranus_bigtts），不指定则随机选")
    p_gen_voice.add_argument("--instruction", help="自然语言情感指令，控制语气语调（如 \"用凶狠霸道的语气说\"）")
    p_gen_voice.add_argument("--emotion", help="情感标签（如 angry/happy/sad），写入 audio_params.emotion")
    p_gen_voice.add_argument("--emotion-scale", type=int, choices=range(1, 6), help="情感强度 1-5，需配合 --emotion 使用")
    p_gen_voice.add_argument("--force", action="store_true", help="覆盖已有音色，换一个新音色")

    # fix-image <项目路径> --name --prompt
    p_fix_img = sub.add_parser("fix-image", help="修改图片资产")
    p_fix_img.add_argument("project", help="项目路径")
    p_fix_img.add_argument("--name", required=True, help="资产名称（角色名、角色名:形态名、场景名等）")
    p_fix_img.add_argument("--prompt", required=True, help="修改提示词")

    # reshape-image <项目路径> --name [--regions --width --waist --height --legs --head --inplace]
    p_resh = sub.add_parser("reshape-image", help="身材重塑（瘦胖/高矮/腿比/头比，纯几何变形）")
    p_resh.add_argument("project", help="项目路径")
    p_resh.add_argument("--name", required=True, help="资产名称（角色名、角色名:形态名等）")
    p_resh.add_argument("--regions", required=True, help="各视图语义坐标 JSON（必填，agent 看图标注）")
    p_resh.add_argument("--width", type=float, default=1.0, help="整体宽窄：<1 瘦 / >1 胖")
    p_resh.add_argument("--waist", type=float, default=1.0, help="腰部宽窄：<1 收腰 / >1 腰粗")
    p_resh.add_argument("--height", type=float, default=1.0, help="身高：>1 变高 / <1 变矮")
    p_resh.add_argument("--legs", type=float, default=1.0, help="腿长占比：>1 变长 / <1 变短")
    p_resh.add_argument("--head", type=float, default=1.0, help="头部大小：<1 头小 / >1 头大")
    p_resh.add_argument("--stretch", type=float, default=1.0, help="全身横向均匀缩放（含头部）：>1 拉宽")
    p_resh.add_argument("--inplace", action="store_true", help="覆盖原图（默认输出 -reshape.png 预览）")

    # gen-shots <项目路径> --chapter [--force]
    p_gen_shots = sub.add_parser("gen-shots", help="拆分分镜")
    p_gen_shots.add_argument("project", help="项目路径")
    p_gen_shots.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_gen_shots.add_argument("--force", action="store_true", help="覆盖已有分镜文件")

    # gen-keyframe <项目路径> --chapter --shot [--force]
    p_gen_keyframe = sub.add_parser("gen-keyframe", help="生成分镜首帧图")
    p_gen_keyframe.add_argument("project", help="项目路径")
    p_gen_keyframe.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_gen_keyframe.add_argument("--shot", required=True, help="分镜号（如 001_01 或 001）")
    p_gen_keyframe.add_argument("--anchor", default=None, help="首帧锚点：尾帧/首帧/第一帧/完整标记/none")
    p_gen_keyframe.add_argument("--force", action="store_true", help="覆盖已有 keyframe.png")

    # gen-video <项目路径> --chapter --shot
    p_gen_video = sub.add_parser("gen-video", help="生成分镜视频")
    p_gen_video.add_argument("project", help="项目路径")
    p_gen_video.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_gen_video.add_argument("--shot", required=True, help="分镜号（如 001）")

    # compose-chapter <项目路径> --chapter [--output]
    p_compose = sub.add_parser("compose-chapter", help="合成章节视频")
    p_compose.add_argument("project", help="项目路径")
    p_compose.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_compose.add_argument("--output", default=None, help="输出文件名（默认 chapter.mp4）")
    p_compose.add_argument("--shots-dir", default="shots", help="分镜目录名（默认 shots）")

    return parser


def main(argv=None) -> int:
    # Windows 控制台默认 cp1252 编码，打印中文会崩，强制 UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "init":
        from . import init as init_mod
        return init_mod.main([args.name])

    if cmd == "config-list":
        from . import config_manager
        sub_argv = [args.project, args.subcommand]
        return config_manager.main(sub_argv)

    if cmd == "extract":
        from . import extract as extract_mod
        sub_argv = [args.project, "--chapter", args.chapter]
        if args.confirm:
            sub_argv.append("--confirm")
        return extract_mod.main(sub_argv)

    if cmd == "gen-image":
        from . import gen_image
        sub_argv = [args.project, "--type", args.type, "--name", args.name]
        if args.prompt:
            sub_argv += ["--prompt", args.prompt]
        if args.size:
            sub_argv += ["--size", args.size]
        if args.model:
            sub_argv += ["--model", args.model]
        if args.force:
            sub_argv.append("--force")
        if args.form:
            sub_argv += ["--form", args.form]
        if args.gender:
            sub_argv += ["--gender", args.gender]
        if args.no_voice:
            sub_argv.append("--no-voice")
        if args.ref_image:
            sub_argv += ["--ref-image", args.ref_image]
        if args.designs:
            sub_argv.append("--designs")
        if args.age:
            sub_argv += ["--age", args.age]
        if args.hair:
            sub_argv += ["--hair", args.hair]
        if args.cells and args.cells != 8:
            sub_argv += ["--cells", str(args.cells)]
        if args.face_image:
            sub_argv += ["--face-image", args.face_image]
        if args.costume_image:
            sub_argv += ["--costume-image", args.costume_image]
        return gen_image.main(sub_argv)

    if cmd == "gen-voice":
        from . import gen_voice
        sub_argv = [args.project, "--name", args.name, "--gender", args.gender]
        if args.voice:
            sub_argv += ["--voice", args.voice]
        if args.instruction:
            sub_argv += ["--instruction", args.instruction]
        if args.emotion:
            sub_argv += ["--emotion", args.emotion]
        if args.emotion_scale:
            sub_argv += ["--emotion-scale", str(args.emotion_scale)]
        if args.force:
            sub_argv.append("--force")
        return gen_voice.main(sub_argv)

    if cmd == "fix-image":
        from . import fix_image
        sub_argv = [args.project, "--name", args.name, "--prompt", args.prompt]
        return fix_image.main(sub_argv)

    if cmd == "reshape-image":
        from . import reshape_image
        sub_argv = [args.project, "--name", args.name,
                    "--width", str(args.width), "--waist", str(args.waist),
                    "--height", str(args.height), "--legs", str(args.legs),
                    "--head", str(args.head), "--stretch", str(args.stretch)]
        if args.regions:
            sub_argv += ["--regions", args.regions]
        if args.inplace:
            sub_argv.append("--inplace")
        return reshape_image.main(sub_argv)

    if cmd == "gen-shots":
        from . import gen_shots
        sub_argv = [args.project, "--chapter", args.chapter]
        if args.force:
            sub_argv.append("--force")
        return gen_shots.main(sub_argv)

    if cmd == "gen-keyframe":
        from . import gen_keyframe
        sub_argv = [args.project, "--chapter", args.chapter, "--shot", args.shot]
        if args.anchor:
            sub_argv += ["--anchor", args.anchor]
        if args.force:
            sub_argv.append("--force")
        return gen_keyframe.main(sub_argv)

    if cmd == "gen-video":
        from . import gen_video
        sub_argv = [args.project, "--chapter", args.chapter, "--shot", args.shot]
        return gen_video.main(sub_argv)

    if cmd == "compose-chapter":
        from . import compose_chapter
        sub_argv = [args.project, "--chapter", args.chapter]
        if args.output:
            sub_argv += ["--output", args.output]
        if args.shots_dir:
            sub_argv += ["--shots-dir", args.shots_dir]
        return compose_chapter.main(sub_argv)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
