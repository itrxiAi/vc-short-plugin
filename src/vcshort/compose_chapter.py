#!/usr/bin/env python3
"""合成章节视频：将一个章节下所有分镜的 shot.mp4 按顺序拼接成一个完整视频。

用 imageio-ffmpeg 自带的 ffmpeg 二进制拼接，不依赖系统安装 ffmpeg。
编码为 H.264，兼容所有播放器。
合成后自动读取分镜对白生成 SRT 字幕并烧录到视频中。

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

try:
    import yaml
except ImportError:
    print("错误：需要 pyyaml（pip install pyyaml）", file=sys.stderr)
    sys.exit(1)


def find_shot_dirs(chapter_dir: Path) -> list:
    """按分镜号顺序查找所有 shot_* 目录。"""
    shots_dir = chapter_dir / "shots"
    if not shots_dir.is_dir():
        return []
    dirs = []
    for shot_dir in sorted(shots_dir.iterdir()):
        if shot_dir.is_dir() and shot_dir.name.startswith("shot_"):
            dirs.append(shot_dir)
    return dirs


def find_shot_videos(chapter_dir: Path) -> list:
    """按分镜号顺序查找所有 shot.mp4 文件。"""
    videos = []
    for shot_dir in find_shot_dirs(chapter_dir):
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


def get_video_duration(video_path: Path) -> float:
    """获取视频时长（秒）。"""
    info = get_video_info(video_path)
    if info["fps"] > 0:
        return info["frames"] / info["fps"]
    return 10.0  # 默认 10 秒


def load_shot_dialogue(shot_dir: Path) -> list:
    """读取分镜 YAML 中的对白列表，返回 [{speaker, text, emotion}, ...]。"""
    shot_path = shot_dir / "shot.yaml"
    if not shot_path.exists():
        return []
    with open(shot_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    dialogue = data.get("dialogue")
    if not dialogue:
        return []
    return dialogue


def format_srt_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间格式：HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(shot_dirs: list, video_durations: list) -> str:
    """根据分镜对白和时间轴生成 SRT 字幕内容。

    每个分镜的对白在该分镜的时间段内均匀分布。
    """
    srt_lines = []
    index = 1
    current_time = 0.0

    for i, shot_dir in enumerate(shot_dirs):
        duration = video_durations[i] if i < len(video_durations) else 10.0
        dialogue = load_shot_dialogue(shot_dir)
        if not dialogue:
            current_time += duration
            continue

        # 在该分镜时间段内均匀分配对白
        lines_count = len(dialogue)
        per_line = duration / lines_count

        for j, d in enumerate(dialogue):
            start = current_time + j * per_line
            end = current_time + (j + 1) * per_line
            # 最后一句留一点尾音
            if j == lines_count - 1:
                end = current_time + duration

            speaker = d.get("speaker", "")
            text = d.get("text", "")
            if not text:
                continue

            # 字幕内容：带说话人
            if speaker:
                subtitle_text = f"{speaker}：{text}"
            else:
                subtitle_text = text

            srt_lines.append(str(index))
            srt_lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
            srt_lines.append(subtitle_text)
            srt_lines.append("")
            index += 1

        current_time += duration

    return "\n".join(srt_lines)


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


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> None:
    """用 ffmpeg 将 SRT 字幕烧录到视频中。"""
    # ffmpeg subtitles filter，需要转义路径中的特殊字符
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{srt_escaped}':force_style='FontName=PingFang SC,FontSize=22,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=30'"

    cmd = [
        FFMPEG, "-y",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"字幕烧录失败:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort compose-chapter", description="合成章节视频")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--output", default=None, help="输出文件名（默认 chapter.mp4）")
    parser.add_argument("--no-subtitle", action="store_true", help="不烧录字幕")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    chapter_dir = project_root / "chapters" / args.chapter
    if not chapter_dir.is_dir():
        print(f"错误：章节目录不存在: {chapter_dir}", file=sys.stderr)
        return 1

    shot_dirs = find_shot_dirs(chapter_dir)
    videos = find_shot_videos(chapter_dir)
    if not videos:
        print(f"错误：{chapter_dir}/shots/ 下没有找到 shot.mp4 文件", file=sys.stderr)
        return 1

    print(f"找到 {len(videos)} 个分镜视频:")
    for v in videos:
        print(f"  {v}")

    output_name = args.output or "chapter.mp4"
    output_path = chapter_dir / output_name

    # 1. 拼接视频
    print(f"\n正在合成...")
    compose(videos, output_path)
    print(f"✅ 拼接完成: {output_path}")

    # 2. 生成并烧录字幕
    if not args.no_subtitle:
        print(f"\n正在生成字幕...")
        # 获取每个分镜视频的实际时长
        video_durations = [get_video_duration(v) for v in videos]

        # 生成 SRT
        srt_content = generate_srt(shot_dirs, video_durations)
        srt_path = chapter_dir / "chapter.srt"

        if srt_content.strip():
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            print(f"✅ 字幕已生成: {srt_path}")

            # 烧录字幕
            print(f"正在烧录字幕...")
            temp_output = chapter_dir / "chapter_temp.mp4"
            burn_subtitles(output_path, srt_path, temp_output)
            # 替换原文件
            output_path.unlink()
            temp_output.rename(output_path)
            print(f"✅ 字幕已烧录到视频")
        else:
            print("ℹ️ 没有对白内容，跳过字幕")

    print(f"\n✅ 章节视频合成完成")
    print(f"   输出: {output_path}")
    print(f"   分镜数: {len(videos)}")
    return 0
