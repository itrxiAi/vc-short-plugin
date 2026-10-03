#!/usr/bin/env python3
"""采集小说章节：网页滚动截图存档，供 Agent 读图转写为 novel.md。

依赖系统 python3 + playwright（插件的便携 Python 不含 playwright）：
    python3 -m pip install playwright
    python3 -m playwright install chromium

用法：
    python3 capture_novel.py \
        --url "https://fanqienovel.com/reader/<id>" \
        --project /path/to/project \
        --start-chapter 11 --chapters 5 --skip 1

产物（每章）：
    <project>/.crawl/ch<NN>/chunks/chunk_0001.png ...
    <project>/.crawl/ch<NN>/preview.png
    <project>/.crawl/ch<NN>/crawl.json

Agent 读完截图写入 <project>/chapters/ch<NN>/novel.md 后，删除 <project>/.crawl。

退出码：
    0  全部完成
    2  遇到付费墙，已停止（该章及之后未采集）
    1  其他错误
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright


# 付费墙特征文案（阅读页正文用自定义字体混淆，但这些 UI 文案是正常文本）
PAYWALL_MARKERS = (
    "SVIP网页畅读",
    "扫码下载APP免费读",
    "会员登录后，可在网页畅读全文",
    "购买SVIP还可享受网页畅读权益",
)

# 一次调用内完成「滚动 + 读回真实状态」，避免跨调用引用滚动容器
JS_SCROLL = """(pos) => {
  const doc = document.scrollingElement;
  const all = [doc, ...document.querySelectorAll('*')].filter(Boolean);
  const scrollable = all.filter((el) => {
    const s = getComputedStyle(el);
    const oy = s.overflowY;
    return (oy === 'auto' || oy === 'scroll' || el === doc)
      && el.scrollHeight - el.clientHeight > 50;
  });
  scrollable.sort((a, b) =>
    (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
  const root = scrollable[0] || doc;
  if (root === doc) window.scrollTo(0, pos); else root.scrollTop = pos;
  const isDoc = root === doc;
  return {
    top: Math.round(isDoc ? window.scrollY : root.scrollTop),
    height: Math.round(root.scrollHeight),
    viewport: Math.round(root.clientHeight),
  };
}"""

JS_IMAGES_READY = "Array.from(document.images).every((i) => i.complete)"


def parse_chapter_no(value: str) -> int:
    text = str(value).strip().lower()
    if text.startswith("ch"):
        text = text[2:]
    if not re.fullmatch(r"\d+", text):
        raise argparse.ArgumentTypeError(f"章节号应为 ch11 或 11，收到：{value}")
    return int(text)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="采集小说章节：滚动截图存档，供 Agent 读图转写",
    )
    parser.add_argument("--url", required=True, help="起始章节的阅读页 URL")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument(
        "--start-chapter", required=True, type=parse_chapter_no,
        help="起始章节号（ch11 或 11），用于命名 .crawl/ch<NN> 与报告",
    )
    parser.add_argument("--chapters", type=int, default=1, help="连续采集章数")
    parser.add_argument(
        "--skip", type=int, default=0,
        help="采集前先点几次「下一章」（起始 URL 不是要采的第一章时用）",
    )
    parser.add_argument("--overlap", type=float, default=0.2, help="截图重叠比例，0~0.8")
    parser.add_argument("--wait-ms", type=int, default=700, help="页面变化/滚动后的等待毫秒")
    parser.add_argument("--max-scrolls", type=int, default=200, help="单章滚动次数上限")
    parser.add_argument("--max-chunks", type=int, default=40, help="单章截图张数上限（防滚动失控）")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（用于人工登录）")
    args = parser.parse_args(argv)

    if args.chapters < 1:
        raise SystemExit("--chapters 至少为 1")
    if args.skip < 0:
        raise SystemExit("--skip 不能为负")
    if args.start_chapter < 1:
        raise SystemExit("--start-chapter 至少为 1")
    if not 0 <= args.overlap < 0.8:
        raise SystemExit("--overlap 需在 0~0.8 之间")
    return args


def wait_for_page(page, wait_ms: int) -> None:
    """等待页面稳定：定时、字体、图片。"""
    page.wait_for_timeout(wait_ms)
    try:
        page.evaluate("document.fonts && document.fonts.ready")
    except Exception:
        pass
    try:
        page.wait_for_function(JS_IMAGES_READY, timeout=max(2000, wait_ms * 4))
    except PWTimeout:
        pass


def detect_paywall(page) -> str | None:
    """命中付费墙特征文案则返回该文案，否则返回 None。"""
    try:
        text = page.inner_text("body")
    except Exception:
        return None
    for marker in PAYWALL_MARKERS:
        if marker in text:
            return marker
    return None


def find_next_button(page, wait_ms: int):
    """轮询查找可点击的「下一章」，规避冷启动时序竞态。"""
    deadline_ms = max(15000, wait_ms * 10)
    waited = 0
    candidates = (
        lambda: page.get_by_role("button", name="下一章", exact=True),
        lambda: page.get_by_text("下一章", exact=True),
        lambda: page.locator("text=下一章"),
    )
    while waited < deadline_ms:
        for make in candidates:
            try:
                locator = make()
                count = locator.count()
            except Exception:
                continue
            for index in range(count - 1, -1, -1):
                element = locator.nth(index)
                try:
                    if element.is_visible() and element.is_enabled():
                        return element
                except Exception:
                    continue
        page.wait_for_timeout(500)
        waited += 500
    return None


def click_next(page, button, wait_ms: int) -> None:
    old_url = page.url
    button.scroll_into_view_if_needed()
    button.click()
    try:
        page.wait_for_url(lambda url: str(url) != old_url, timeout=10000)
    except PWTimeout:
        page.wait_for_timeout(wait_ms * 2)
    wait_for_page(page, wait_ms)


def capture_chapter(page, chapter_dir: Path, args: argparse.Namespace) -> dict:
    """滚动截取当前章节，写入 chapter_dir。"""
    chunks_dir = chapter_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    preview_path = chapter_dir / "preview.png"

    page.evaluate(JS_SCROLL, 0)
    wait_for_page(page, args.wait_ms)
    metrics = page.evaluate(JS_SCROLL, 0)
    height = int(metrics["height"])
    viewport = int(metrics["viewport"])
    step = max(1, int(viewport * (1 - args.overlap)))

    images: list[Image.Image] = []
    chunk_paths: list[str] = []
    positions: list[int] = []
    pos = 0
    prev_top = -1
    stalled = 0

    for _ in range(args.max_scrolls):
        metrics = page.evaluate(JS_SCROLL, pos)
        wait_for_page(page, args.wait_ms)
        metrics = page.evaluate(JS_SCROLL, pos)
        top = int(metrics["top"])
        height = max(height, int(metrics["height"]))
        viewport = int(metrics["viewport"])

        shot = Image.open(io.BytesIO(page.screenshot(full_page=False))).convert("RGB")
        remaining = max(1, height - top)
        shot = shot.crop((0, 0, shot.width, min(shot.height, remaining)))

        chunk_path = chunks_dir / f"chunk_{len(images) + 1:04d}.png"
        shot.save(chunk_path, "PNG")
        images.append(shot)
        chunk_paths.append(str(chunk_path))
        positions.append(top)

        if len(images) > args.max_chunks:
            raise RuntimeError(
                f"截图数超过上限 {args.max_chunks}，疑似滚动异常，已中止"
            )

        if top + viewport >= height:
            break

        if top <= prev_top:
            stalled += 1
            if stalled >= 3:
                raise RuntimeError(
                    "页面滚动无进展（scrollTop 不前进），已中止以避免无限截图"
                )
        else:
            stalled = 0
        prev_top = top
        pos = min(pos + step, max(0, height - viewport))
    else:
        raise RuntimeError(f"达到 --max-scrolls({args.max_scrolls}) 仍未到达页面底部")

    stitched_height = sum(image.height for image in images)
    stitched = Image.new("RGB", (max(image.width for image in images), stitched_height), "white")
    offset = 0
    for image in images:
        stitched.paste(image, (0, offset))
        offset += image.height
    stitched.save(preview_path, "PNG", optimize=True)

    return {
        "url": page.url,
        "title": page.title(),
        "chunks_dir": str(chunks_dir),
        "chunk_paths": chunk_paths,
        "preview": str(preview_path),
        "scroll_positions": positions,
        "page_height": height,
        "chunks": len(images),
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    if not (project / "chapters").is_dir():
        print(f"错误：{project} 下没有 chapters/ 目录，请先执行 vcshort init", file=sys.stderr)
        return 1
    work_root = project / ".crawl"

    records: list[dict] = []
    paywall: dict | None = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            wait_for_page(page, args.wait_ms)

            for index in range(args.skip):
                button = find_next_button(page, args.wait_ms)
                if button is None:
                    raise RuntimeError(f"跳过第 {index + 1} 章时未找到可点击的「下一章」按钮")
                click_next(page, button, args.wait_ms)
                print(f"已跳过 1 章，当前：{page.title()}")

            for offset in range(args.chapters):
                number = args.start_chapter + offset
                marker = detect_paywall(page)
                if marker:
                    paywall = {
                        "chapter": number,
                        "chapter_no": f"ch{number:02d}",
                        "marker": marker,
                        "url": page.url,
                        "title": page.title(),
                    }
                    break

                chapter_dir = work_root / f"ch{number:02d}"
                record = capture_chapter(page, chapter_dir, args)
                record["chapter"] = number
                record["chapter_no"] = f"ch{number:02d}"
                record["chapter_dir"] = str(chapter_dir)
                (chapter_dir / "crawl.json").write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                records.append(record)
                print(f"ch{number:02d} 完成：{record['chunks']} 张截图 -> {record['chunks_dir']}")

                if offset < args.chapters - 1:
                    button = find_next_button(page, args.wait_ms)
                    if button is None:
                        raise RuntimeError(f"ch{number:02d} 未找到可点击的「下一章」按钮")
                    click_next(page, button, args.wait_ms)
        finally:
            browser.close()

    print(json.dumps(
        {"records": records, "paywall": paywall, "work_root": str(work_root)},
        ensure_ascii=False,
        indent=2,
    ))

    if paywall:
        print(
            f"⚠️ 检测到付费墙（{paywall['chapter_no']}，命中「{paywall['marker']}」），已停止采集，"
            "不绕过付费墙。",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
