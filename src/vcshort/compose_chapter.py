#!/usr/bin/env python3
"""合成章节视频：将一个章节下所有分镜的 shot.mp4 按顺序拼接成一个完整视频。

用 imageio-ffmpeg 自带的 ffmpeg 二进制拼接，不依赖系统安装 ffmpeg。
编码为 H.264，兼容所有播放器。

用法：
    vcshort compose-chapter <项目路径> --chapter <章节号> [--output <文件名>]

输出默认放在 chapters/<章节号>/chapter.mp4
"""
import argparse
import subprocess
import sys
from pathlib import Path

try:
    import cv2
except ImportError:
    print("错误：需要 opencv-python（pip install opencv-python）", file=sys.stderr)
    sys.exit(1)

try:
    from imageio_ffmpeg import get_ffmpeg_exe
    FFMPEG = get_ffmpeg_exe()
except ImportError:
    print("错误：需要 imageio-ffmpeg（pip install imageio-ffmpeg）", file=sys.stderr)
    sys.exit(1)


def find_shot_videos(chapter_dir: Path) -> list:
    """按分镜号顺序查找所有 shot.mp4 文件。"""
    shots_dir = chapter_dir / "shots"
    if not shots_dir.is_dir():
        return []
    videos = []
    for shot_dir in sorted(shots_dir.iterdir()):
        if shot_dir.is_dir() and shot_dir.name.startswith("shot_"):
            video = shot_dir / "shot.mp4"
            if video.exists():
                videos.append(video)
    return videos


def get_video_info(video_path: Path) -> dict:
    """用 opencv 获取视频信息。"""
    cap = cv2.VideoCapture(str(video_path))
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS) or 24.0,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    return info


def compose(videos: list, output_path: Path) -> None:
    """用 ffmpeg concat demuxer 拼接视频，输出 H.264 编码。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 生成 concat 文件列表
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for v in videos:
            # ffmpeg concat 需要转义单引号
            escaped = str(v).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    # 从第一个视频获取参数
    info = get_video_info(videos[0])
    fps = info["fps"]

    # 用 ffmpeg concat demuxer + 重新编码为 H.264
    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-crf", "18",
        "-preset", "fast",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 错误:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # 清理临时文件
    list_file.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort compose-chapter", description="合成章节视频")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--output", default=None, help="输出文件名（默认 chapter.mp4）")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    chapter_dir = project_root / "chapters" / args.chapter
    if not chapter_dir.is_dir():
        print(f"错误：章节目录不存在: {chapter_dir}", file=sys.stderr)
        return 1

    videos = find_shot_videos(chapter_dir)
    if not videos:
        print(f"错误：{chapter_dir}/shots/ 下没有找到 shot.mp4 文件", file=sys.stderr)
        return 1

    print(f"找到 {len(videos)} 个分镜视频:")
    for v in videos:
        print(f"  {v}")

    output_name = args.output or "chapter.mp4"
    output_path = chapter_dir / output_name

    print(f"\n正在合成...")
    compose(videos, output_path)

    print(f"\n✅ 章节视频合成完成")
    print(f"   输出: {output_path}")
    print(f"   分镜数: {len(videos)}")
    return 0
