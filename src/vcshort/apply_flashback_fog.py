#!/usr/bin/env python3
"""回忆/闪回视频后处理：给画面边缘叠加一圈白色雾气。"""

import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def apply_flashback_fog(
    video_path: str | Path,
    output_path: str | Path | None = None,
    inner: float = 0.55,
    outer: float = 1.0,
    max_alpha: float = 0.75,
    gamma: float = 2.0,
) -> Path:
    """给视频叠加边缘白雾，返回输出视频路径。

    参数（已按 004_01 效果固定）：
      - inner: 中心清晰区半径比例（0~1），默认 0.55
      - outer: 雾完全覆盖区半径比例，默认 1.0
      - max_alpha: 边缘最大雾浓度，默认 0.75
      - gamma: 雾浓度曲线幂次，默认 2.0（越靠边越浓）
    """
    if cv2 is None or np is None:
        print("错误：回忆雾效需要 opencv-python 和 numpy，请安装：pip install opencv-python numpy", file=sys.stderr)
        sys.exit(1)
    if not _has_ffmpeg():
        print("错误：回忆雾效需要 ffmpeg", file=sys.stderr)
        sys.exit(1)

    video_path = Path(video_path)
    if output_path is None:
        output_path = video_path
    else:
        output_path = Path(output_path)

    # 临时文件
    tmp_dir = Path(tempfile.gettempdir())
    video_no_audio = tmp_dir / f"{video_path.stem}_fog_no_audio.mp4"
    audio_path = tmp_dir / f"{video_path.stem}_audio.aac"

    try:
        # 提取音频
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-c:a", "copy", str(audio_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

        # 读取视频
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"错误：无法打开视频 {video_path}", file=sys.stderr)
            sys.exit(1)

        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video_no_audio), fourcc, fps, (w, h))

        # 径向雾遮罩：中心清晰，边缘白色
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        xx, yy = np.meshgrid(x, y)
        dist = np.sqrt(xx**2 + yy**2)
        alpha = np.clip((dist - inner) / (outer - inner), 0, 1)
        alpha = (alpha ** gamma) * max_alpha
        alpha = alpha[:, :, np.newaxis].astype(np.float32)

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_f = frame.astype(np.float32)
            fogged = frame_f * (1 - alpha) + 255.0 * alpha
            fogged = np.clip(fogged, 0, 255).astype(np.uint8)
            out.write(fogged)
            frame_count += 1

        cap.release()
        out.release()
        print(f"回忆雾效处理 {frame_count} 帧")

        # 合并音频
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_no_audio),
                "-i", str(audio_path),
                "-c:v", "libx264", "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(output_path),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        print(f"已保存回忆雾效视频: {output_path}")
    finally:
        # 清理临时文件
        if video_no_audio.exists():
            video_no_audio.unlink()
        if audio_path.exists():
            audio_path.unlink()

    return output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="apply_flashback_fog", description="给视频叠加回忆白雾")
    parser.add_argument("video", help="输入视频路径")
    parser.add_argument("-o", "--output", default=None, help="输出路径（默认覆盖输入）")
    args = parser.parse_args(argv)
    apply_flashback_fog(args.video, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
