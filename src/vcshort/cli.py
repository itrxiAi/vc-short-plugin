#!/usr/bin/env python3
"""vcshort CLI 主入口 — AI 短视频制作命令行工具。

用法：
    vcshort <command> [args...]

子命令：
    init              初始化项目
    config-list       列出已有资产
    extract           提取资产并匹配
    gen-image         生成图片资产
    fix-image         修改图片资产
    gen-shots         拆分分镜
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

    # gen-image <项目路径> --type --name --prompt [--form] [--size] [--model] [--force]
    p_gen_img = sub.add_parser("gen-image", help="生成图片资产")
    p_gen_img.add_argument("project", help="项目路径")
    p_gen_img.add_argument("--type", required=True, choices=["character", "costume", "prop", "scene"], help="资产类型")
    p_gen_img.add_argument("--name", required=True, help="资产名称")
    p_gen_img.add_argument("--prompt", required=True, help="生成提示词")
    p_gen_img.add_argument("--size", default="2K", help="图片尺寸 (2K/3K/4K)")
    p_gen_img.add_argument("--model", default=None, help="模型 ID（默认读 config.yaml）")
    p_gen_img.add_argument("--force", action="store_true", help="覆盖同名资产")
    p_gen_img.add_argument("--form", default=None, help="角色形态名（仅 type=character）")

    # fix-image <项目路径> --name --prompt
    p_fix_img = sub.add_parser("fix-image", help="修改图片资产")
    p_fix_img.add_argument("project", help="项目路径")
    p_fix_img.add_argument("--name", required=True, help="资产名称（角色名、角色名:形态名、场景名等）")
    p_fix_img.add_argument("--prompt", required=True, help="修改提示词")

    # gen-shots <项目路径> --chapter [--force]
    p_gen_shots = sub.add_parser("gen-shots", help="拆分分镜")
    p_gen_shots.add_argument("project", help="项目路径")
    p_gen_shots.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    p_gen_shots.add_argument("--force", action="store_true", help="覆盖已有分镜文件")

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

    return parser


def main(argv=None) -> int:
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
        sub_argv = [args.project, "--type", args.type, "--name", args.name, "--prompt", args.prompt]
        if args.size:
            sub_argv += ["--size", args.size]
        if args.model:
            sub_argv += ["--model", args.model]
        if args.force:
            sub_argv.append("--force")
        if args.form:
            sub_argv += ["--form", args.form]
        return gen_image.main(sub_argv)

    if cmd == "fix-image":
        from . import fix_image
        sub_argv = [args.project, "--name", args.name, "--prompt", args.prompt]
        return fix_image.main(sub_argv)

    if cmd == "gen-shots":
        from . import gen_shots
        sub_argv = [args.project, "--chapter", args.chapter]
        if args.force:
            sub_argv.append("--force")
        return gen_shots.main(sub_argv)

    if cmd == "gen-video":
        from . import gen_video
        sub_argv = [args.project, "--chapter", args.chapter, "--shot", args.shot]
        return gen_video.main(sub_argv)

    if cmd == "compose-chapter":
        from . import compose_chapter
        sub_argv = [args.project, "--chapter", args.chapter]
        if args.output:
            sub_argv += ["--output", args.output]
        return compose_chapter.main(sub_argv)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
