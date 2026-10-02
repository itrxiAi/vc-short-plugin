#!/usr/bin/env python3
"""身材重塑 — 纯几何变形（液化原理），不调用任何 AI/API

用法：
  vcshort reshape-image <项目路径> --name <资产名> [选项]
  vcshort reshape-image <项目路径> --name <角色名:形态名> --regions '[{...}]'

变形维度（均为缩放系数，1.0 = 不变）：
  --width   整体宽窄：<1 变瘦，>1 变胖（肩部以下生效）
  --waist   腰部宽窄：<1 收腰，>1 腰粗（腰部高斯衰减）
  --stretch 整体横向缩放（含头部，最简单粗暴的拉宽/压扁）
  --height  身高：>1 变高，<1 变矮（脚底固定）
  --legs    腿长占比：>1 腿变长（躯干缩短补差），<1 腿变短
  --head    头部大小：<1 头小，>1 头大

纵向分段：头 [top,neck] / 躯干 [neck,hip] / 腿 [hip,bottom]
身高=三段之和；躯干为浮动段自动补齐，脚底锚定不动。

--regions JSON 每项（由 agent 看图标注）：
  {"x": [x0, x1],          # 视图横向范围（必填，单位像素）
   "cx": 380,              # 人物中轴 x（缺省取 x 范围中点）
   "top_y": 75,            # 头顶 y（缺省取范围内人物最高像素）
   "bottom_y": 1590,       # 脚底 y（缺省取范围内人物最低像素）
   "neck_y": 330,          # 脖子/头身分界 y（下巴领口下沿）——必填
   "shoulder_y": 400,      # 肩线 y（手臂根部）——缺省 neck_y+0.06h
   "waist_y": 660,         # 腰 y（肘部高度）——必填；收腰/肚腩的峰值位置
   "hip_y": 870,           # 胯部/腿根 y（手腕高度）——必填
   "sigma": 0.06,          # 腰部高斯宽度（占身高比例，缺省 0.10；肚腩用 0.05~0.07）
   "torso_x": [x0, x1],    # 腰高处躯干的左右边界（可省略）：限定 --waist 凸起
                          # 只作用于躯干剪影内，手臂/缝隙不受影响
   "arms": [[x0, x1], ...]}# 手臂列范围（可省略，被 torso_x 取代）：范围内
                          # 不受 --waist 影响，防止手臂内缘推得比外缘多导致变细
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from .fix_image import find_asset_image


def figure_mask(img: np.ndarray) -> np.ndarray:
    """非背景像素掩码：背景取四角灰度中位数，阈值自适应。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners = [gray[0, 0], gray[0, -1], gray[-1, 0], gray[-1, -1]]
    bg = float(np.median(corners))
    thr = min(bg - 10, 235)
    return (gray < max(thr, 60)).astype(np.uint8)


def region_geometry(mask: np.ndarray, x0: int, x1: int) -> dict:
    """在视图范围内求人物包围盒（机械量测，非语义估计）。"""
    sub = mask[:, x0:x1]
    rows = np.where(sub.sum(axis=1) > 2)[0]
    cols = np.where(sub.sum(axis=0) > 2)[0]
    if len(rows) < 10 or len(cols) < 10:
        return None
    top, bot = int(rows[0]), int(rows[-1])
    fx0, fx1 = x0 + int(cols[0]), x0 + int(cols[-1])
    return {"x": [x0, x1], "cx": (fx0 + fx1) / 2, "top_y": top,
            "bottom_y": bot, "fx0": fx0, "fx1": fx1, "h": bot - top}


def apply_reshape(img: np.ndarray, region: dict, width: float, waist: float,
                  height: float, legs: float, head: float, stretch: float,
                  bg_color: np.ndarray) -> np.ndarray:
    """对一个视图区域施加横向（宽窄/腰）+ 纵向（身高/腿长/头身比）变形。"""
    H, W = img.shape[:2]
    x0, x1 = int(region["x"][0]), int(region["x"][1])
    cx = float(region["cx"])
    top, bot = int(region["top_y"]), int(region["bottom_y"])
    neck = float(region["neck_y"])
    waist_y = float(region["waist_y"])
    hip = float(region["hip_y"])
    h = bot - top
    if h < 50:
        return img

    # ---------- 纵向：三段比例 ----------
    head_src, torso_src, leg_src = neck - top, hip - neck, bot - hip
    target_h = h * height
    head_dst = head_src * head
    leg_dst = leg_src * legs
    torso_dst = target_h - head_dst - leg_dst
    if torso_dst <= 10:
        print(f"警告：x{region['x']} 参数过大（躯干无空间），已跳过该视图",
              file=sys.stderr)
        return img
    # 脚底锚定：从底部向上排布 腿→躯干→头
    b3, b2, b1, b0 = float(bot), bot - leg_dst, bot - leg_dst - torso_dst, bot - target_h
    ys = np.arange(H, dtype=np.float32)
    src_y = ys.copy()
    in_fig = (ys >= max(b0, top - 0.05 * h)) & (ys <= bot + 0.02 * h)
    seg = np.searchsorted([b1, b2, b3], ys, side="right")  # 0头 1躯干 2腿 3以下
    da = np.array([b0, b1, b2, b3]); db = np.array([b1, b2, b3, b3 + 1])
    sa = np.array([top, neck, hip, bot]); sb = np.array([neck, hip, bot, bot])
    i = np.clip(seg, 0, 3)
    mapped = sa[i] + (ys - da[i]) / np.maximum(db[i] - da[i], 1e-6) * (sb[i] - sa[i])
    src_y[in_fig] = np.clip(mapped, top - 0.02 * h, bot)[in_fig]

    # ---------- 横向：整体宽窄 + 腰部 ----------
    sigma = float(region.get("sigma", 0.10)) * h
    # 目标图中肩线位置（宽窄变形从这里开始，头/颈不受 --width 影响）
    shoulder_y = b1 + (float(region.get("shoulder_y", neck + 0.06 * h)) - neck) \
        / max(torso_src, 1e-6) * torso_dst
    waist_dst = b1 + (waist_y - neck) / max(torso_src, 1e-6) * torso_dst
    ramp = np.clip((ys - shoulder_y) / 20.0, 0.0, 1.0)
    f_body = (1.0 + (width - 1.0) * ramp) * stretch      # <1 收窄 >1 变宽
    # 头部横向同步缩放：颈线以上乘 head，颈线下 25px 过渡到躯干系数
    f_head = stretch * head
    blend = np.clip((ys - (b1 - 25.0)) / 25.0, 0.0, 1.0)
    f = f_head * (1.0 - blend) + f_body * blend
    f = np.where(in_fig, f, 1.0)
    f = np.clip(f, 0.5, 2.0)

    xs = np.arange(W, dtype=np.float32)
    map_x = np.tile(xs, (H, 1))
    map_y = np.tile(ys.reshape(-1, 1), (1, W))
    xr = xs[x0:x1]
    rows = np.where(in_fig)[0]

    # 腰部：以 (cx, waist_dst) 为中心的膨胀场。
    # rx 收紧到躯干半宽×0.9：手臂/下摆角离中轴远，位移指数衰减，
    # 保证腰部边缘位移最大（而不是最宽的下摆位移最大）
    ry = sigma
    rx = max(cx - region["fx0"], region["fx1"] - cx) * 0.9
    g2d = np.exp(-((xr - cx) / rx)[None, :] ** 4) \
        * np.exp(-((ys[rows] - waist_dst) / ry)[:, None] ** 2)
    # 躯干边界：--waist 凸起只作用于腰高处躯干剪影范围内
    tx = region.get("torso_x")
    if tx:
        dist_out = np.maximum(np.maximum(tx[0] - xr, xr - tx[1]), 0.0)
        g2d *= np.clip(1.0 - dist_out / 12.0, 0.0, 1.0)[None, :]
    # 手臂保护：指定列范围内衰减腰部凸起，避免手臂内缘位移多于外缘
    for ax0, ax1 in region.get("arms") or []:
        dist = np.maximum(np.maximum(ax0 - xr, xr - ax1), 0.0)
        g2d *= np.clip(dist / 15.0, 0.0, 1.0)[None, :]
    Fw = f[rows, None] * (1.0 + (waist - 1.0) * g2d)
    map_x[np.ix_(rows, np.arange(x0, x1))] = cx + (xr - cx)[None, :] / Fw
    map_y[np.ix_(rows, np.arange(x0, x1))] = \
        np.tile(src_y[rows].reshape(-1, 1), (1, x1 - x0))

    out = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE)

    # 变矮时新头顶低于原头顶，清掉原头部残留像素
    if b0 > top:
        ex0 = max(int(region["fx0"]) - int(0.04 * h), x0)
        ex1 = min(int(region["fx1"]) + int(0.04 * h), x1)
        out[top:int(b0) + 1, ex0:ex1] = bg_color

    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort reshape-image",
                                   description="身材重塑（纯几何变形，非 AI；系数 1.0=不变）")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--name", required=True,
                        help="资产名称（角色名、角色名:形态名等）")
    parser.add_argument("--regions", required=True,
                        help="各视图语义坐标 JSON（必填，由 agent 看图标注）")
    parser.add_argument("--width", type=float, default=1.0,
                        help="整体宽窄：<1 瘦 / >1 胖（肩部以下）")
    parser.add_argument("--waist", type=float, default=1.0,
                        help="腰部宽窄：<1 收腰 / >1 腰粗")
    parser.add_argument("--height", type=float, default=1.0,
                        help="身高：>1 变高 / <1 变矮（脚固定）")
    parser.add_argument("--legs", type=float, default=1.0,
                        help="腿长占比：>1 腿变长 / <1 变短")
    parser.add_argument("--head", type=float, default=1.0,
                        help="头部大小：<1 头小 / >1 头大")
    parser.add_argument("--stretch", type=float, default=1.0,
                        help="全身横向均匀缩放（含头部）：>1 拉宽 / <1 压窄")
    parser.add_argument("--inplace", action="store_true",
                        help="覆盖原图（原图备份 .bak）；默认输出 -reshape.png 预览")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    image_path = find_asset_image(project_root, args.name)
    print(f"找到资产: {args.name}")
    print(f"  图片: {image_path}")

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"错误：无法读取图片 {image_path}", file=sys.stderr)
        return 1
    mask = figure_mask(img)

    # 视图语义位置必须由 agent 看图标注传入，不做自动估计
    regions = []
    for r in json.loads(args.regions):
        missing = [k for k in ("x", "neck_y", "waist_y", "hip_y") if k not in r]
        if missing:
            print(f"错误：region 缺少必填字段 {missing}: {r}", file=sys.stderr)
            return 1
        x0, x1 = int(r["x"][0]), int(r["x"][1])
        g = region_geometry(mask, x0, x1)
        if g is None:
            print(f"警告：区域 {r['x']} 内未检测到人物，跳过", file=sys.stderr)
            continue
        g.update({k: v for k, v in r.items() if v is not None})
        g["is_body"] = True
        regions.append(g)

    body_regions = [r for r in regions if r.get("is_body")]
    print(f"共标注 {len(body_regions)} 个全身视图")
    for r in body_regions:
        print(f"  x{r['x']} 颈y={r['neck_y']} 腰y={r['waist_y']} "
              f"胯y={r['hip_y']} 身高={r['bottom_y'] - r['top_y']}px")

    bg_color = np.median(img[mask == 0].reshape(-1, 3), axis=0)
    out = img
    for r in body_regions:
        out = apply_reshape(out, r, args.width, args.waist,
                            args.height, args.legs, args.head,
                            args.stretch, bg_color)

    if args.inplace:
        backup = image_path.with_suffix(image_path.suffix + ".bak")
        image_path.rename(backup)
        out_path = image_path
        print(f"原图备份: {backup}")
    else:
        out_path = image_path.with_name(
            image_path.stem + "-reshape" + image_path.suffix)
    cv2.imwrite(str(out_path), out)
    print(f"已保存: {out_path}")
    print(f"\n✅ '{args.name}' 重塑完成"
          f"（宽 {args.width} 腰 {args.waist} 高 {args.height} "
          f"腿 {args.legs} 头 {args.head}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
