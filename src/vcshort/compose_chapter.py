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
import tempfile
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


def find_shot_videos(chapter_dir: Path, shots_dir_name: str = "shots") -> list:
    """按分镜号顺序查找指定分镜目录下的所有 shot.mp4 文件。"""
    shots_dir = chapter_dir / shots_dir_name
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
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info = {
        "fps": fps,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "frames": frames,
        "duration": frames / fps if fps else 0.0,
    }
    cap.release()
    return info


def has_audio(video_path: Path) -> bool:
    """检测视频是否包含音频流，供黑屏片段补齐静音音轨。"""
    result = subprocess.run(
        [FFMPEG, "-i", str(video_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    return "Audio:" in result.stderr


def scene_id(video_path: Path) -> str:
    """从 shot_001_09 目录名提取场景主编号 001。"""
    name = video_path.parent.name.removeprefix("shot_")
    return name.split("_", 1)[0]


def scene_name(video_path: Path) -> str:
    """读取分镜 YAML 中的场景名，用作转场提示。"""
    yaml_path = video_path.parent / "shot.yaml"
    if yaml_path.exists():
        for line in yaml_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("scene:"):
                return line.split(":", 1)[1].strip().strip("'\\\"")
    return scene_id(video_path)


def find_font() -> str | None:
    """查找可显示中文的字体；找不到时交给 ffmpeg 默认字体。"""
    candidates = [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    return next((path for path in candidates if Path(path).exists()), None)


def escape_drawtext(text: str) -> str:
    """转义 ffmpeg drawtext 的文本内容。"""
    return text.replace("\\\\", "\\\\\\\\").replace(":", "\\\\:").replace("'", "\\\\'")


def run_ffmpeg(command: list) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 错误:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def render_clip(
    video_path: Path,
    output_path: Path,
    info: dict,
    audio: bool,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    scene_label: str = "",
) -> None:
    """为场景边界添加淡入/淡出黑屏效果和场景提示，并统一编码参数。"""
    filters = []
    if fade_in > 0:
        filters.append(f"fade=t=in:st=0:d={fade_in:.3f}:color=black")
    if fade_out > 0:
        start = max(0.0, info["duration"] - fade_out)
        filters.append(f"fade=t=out:st={start:.3f}:d={fade_out:.3f}:color=black")
    if scene_label:
        label_start = 0.0
        label_fade = 0.4
        label_hold_end = label_fade + 1.0
        label_end = label_hold_end + label_fade
        alpha = (
            f"if(lt(t\\,{label_fade})\\,t/{label_fade}\\,"
            f"if(lt(t\\,{label_hold_end})\\,1\\,"
            f"if(lt(t\\,{label_end})\\,({label_end}-t)/{label_fade}\\,0)))"
        )
        font = find_font()
        font_option = f":fontfile='{font}'" if font else ""
        text = escape_drawtext(scene_label)
        filters.append(
            f"drawtext=text='{text}'{font_option}:x=40:y=40:fontsize=48:"
            f"fontcolor=white:borderw=2:bordercolor=black@0.8:shadowx=2:shadowy=2:"
            f"shadowcolor=black@0.65:alpha='{alpha}'"
        )

    command = [FFMPEG, "-y", "-i", str(video_path)]
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-map", "0:v:0", "-c:v", "libx264", "-crf", "18", "-preset", "fast"]
    if audio:
        command += ["-map", "0:a:0?", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
    else:
        command += ["-an"]
    command += ["-r", str(info["fps"]), "-pix_fmt", "yuv420p", str(output_path)]
    run_ffmpeg(command)


def render_black(output_path: Path, info: dict, audio: bool, duration: float) -> None:
    """生成场景之间的短暂黑屏，音频存在时补静音。"""
    size = f"{info['width']}x{info['height']}"
    command = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={size}:r={info['fps']}:d={duration:.3f}",
    ]
    if audio:
        command += [
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
        ]
    else:
        command += ["-map", "0:v:0", "-an"]
    command += [
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-r", str(info["fps"]), "-pix_fmt", "yuv420p", str(output_path),
    ]
    run_ffmpeg(command)


def compose(videos: list, output_path: Path) -> None:
    """拼接视频，并在场景边界淡出黑屏、短暂黑屏后淡入下一场景。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fade_duration = 0.25
    black_duration = 0.0
    info = get_video_info(videos[0])
    audio = has_audio(videos[0])

    with tempfile.TemporaryDirectory(prefix="compose_") as temp_dir:
        temp_dir = Path(temp_dir)
        rendered = []
        for index, video in enumerate(videos):
            previous_scene = scene_id(videos[index - 1]) if index else None
            next_scene = scene_id(videos[index + 1]) if index + 1 < len(videos) else None
            current_scene = scene_id(video)
            is_scene_start = index > 0 and current_scene != previous_scene
            is_scene_end = index + 1 < len(videos) and current_scene != next_scene
            clip_info = get_video_info(video)
            clip_path = temp_dir / f"clip_{index:04d}.mp4"
            render_clip(
                video,
                clip_path,
                clip_info,
                audio,
                fade_in=min(fade_duration, clip_info["duration"] / 2) if is_scene_start else 0.0,
                fade_out=min(fade_duration, clip_info["duration"] / 2) if is_scene_end else 0.0,
                scene_label=scene_name(video) if is_scene_start else "",
            )
            rendered.append(clip_path)
            if is_scene_end and black_duration > 0:
                black_path = temp_dir / f"black_{index:04d}.mp4"
                render_black(black_path, info, audio, black_duration)
                rendered.append(black_path)

        list_file = temp_dir / "concat_list.txt"
        with list_file.open("w", encoding="utf-8") as file:
            for clip in rendered:
                escaped = str(clip).replace("'", "'\\''")
                file.write(f"file '{escaped}'\n")

        run_ffmpeg([
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-r", str(info["fps"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            *(["-c:a", "aac", "-ar", "48000", "-ac", "2"] if audio else ["-an"]),
            str(output_path),
        ])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort compose-chapter", description="合成章节视频")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--chapter", required=True, help="章节号（如 ch01）")
    parser.add_argument("--output", default=None, help="输出文件名（默认 chapter.mp4）")
    parser.add_argument("--shots-dir", default="shots", help="分镜目录名（默认 shots）")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    chapter_dir = project_root / "chapters" / args.chapter
    if not chapter_dir.is_dir():
        print(f"错误：章节目录不存在: {chapter_dir}", file=sys.stderr)
        return 1

    videos = find_shot_videos(chapter_dir, args.shots_dir)
    if not videos:
        print(f"错误：{chapter_dir}/{args.shots_dir}/ 下没有找到 shot.mp4 文件", file=sys.stderr)
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
