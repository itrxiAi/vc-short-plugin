"""裁格工具：把 N列×M行网格图中的指定格裁出来。

用法:
    python3 crop_cell.py <输入图> <输出图> --cell <格号> [--cols 4] [--rows 2]

格号从左上起按行数: 4×2 网格中 1-4 为第一排、5-8 为第二排。
"""
import argparse
import sys

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入网格图路径")
    ap.add_argument("output", help="输出裁格图路径")
    ap.add_argument("--cell", type=int, required=True, help="格号（左上起按行数，1 起）")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=2)
    args = ap.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        sys.exit(f"无法读取图片: {args.input}")

    h, w = img.shape[:2]
    cell_h, cell_w = h // args.rows, w // args.cols
    n = args.cell - 1
    r, c = n // args.cols, n % args.cols
    if not (0 <= n < args.cols * args.rows):
        sys.exit(f"格号 {args.cell} 超出 {args.cols}列×{args.rows}行 网格范围")

    crop = img[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
    cv2.imwrite(args.output, crop)
    print(f"已保存 {args.output}  (格{args.cell}: y[{r*cell_h}:{(r+1)*cell_h}] x[{c*cell_w}:{(c+1)*cell_w}])")


if __name__ == "__main__":
    main()
