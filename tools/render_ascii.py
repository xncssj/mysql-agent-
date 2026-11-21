#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Markdown 中的 ASCII 框线图渲染为 PNG。

为什么不用字体直接画：box-drawing 字符（┌─┐│）在中日韩字体里宽度是中文的 1.5~3 倍，
直接 draw.text 必然错位。这里改为「制表符画线段、其余字符画文字」，
按列推进（ASCII 1 列、中文 2 列），保证与原图对齐。

用法：
    python tools/render_ascii.py                  # 渲染全部候选块
    python tools/render_ascii.py --file 00-全书导读与架构总览.md --line 26
    python tools/render_ascii.py --list           # 只列出候选，不渲染
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

BOX = set("┌┐└┘├┤┬┴┼─│╔╗╚╝║═╠╣╦╩╬")
# 每个制表符占用的方向：l 左 r 右 u 上 d 下
DIRS = {
    "─": "lr", "│": "ud",
    "┌": "rd", "┐": "ld", "└": "ru", "┘": "lu",
    "├": "rud", "┤": "lud", "┬": "lrd", "┴": "lru", "┼": "lrud",
    "═": "lr", "║": "ud",
    "╔": "rd", "╗": "ld", "╚": "ru", "╝": "lu",
    "╠": "rud", "╣": "lud", "╦": "lrd", "╩": "lru", "╬": "lrud",
}

CJK_FONTS = [
    "/usr/share/fonts/cesi/CESI_HT_GB18030.TTF",
    "/usr/share/fonts/wps-office/FZFSK.TTF",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
LATIN_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def pick(fonts, size):
    for p in fonts:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise SystemExit(f"找不到可用字体：{fonts}")


def is_wide(ch: str) -> bool:
    """中文/全角字符占 2 列。"""
    return bool(re.match(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]", ch))


def render(lines, out_path, font_size=15, col_w=None, row_h=None, padding=16, bg="#ffffff", fg="#1f2328"):
    col_w = col_w or max(8, int(font_size * 0.62))
    row_h = row_h or int(font_size * 1.35)
    fc = pick(CJK_FONTS, font_size)
    fl = pick(LATIN_FONTS, font_size)

    max_cols = 0
    for ln in lines:
        w = sum(2 if is_wide(ch) else 1 for ch in ln)
        max_cols = max(max_cols, w)
    width = max_cols * col_w + padding * 2
    height = len(lines) * row_h + padding * 2
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    lw = max(1, font_size // 10)

    for ri, ln in enumerate(lines):
        y0 = padding + ri * row_h
        cy = y0 + row_h // 2
        col = 0
        for ch in ln:
            x0 = padding + col * col_w
            cw = col_w * (2 if is_wide(ch) else 1)
            if ch in DIRS:
                cx = x0 + cw // 2
                dirs = DIRS[ch]
                if "l" in dirs:
                    d.line([(x0, cy), (cx, cy)], fill=fg, width=lw)
                if "r" in dirs:
                    d.line([(cx, cy), (x0 + cw, cy)], fill=fg, width=lw)
                if "u" in dirs:
                    d.line([(cx, y0), (cx, cy)], fill=fg, width=lw)
                if "d" in dirs:
                    d.line([(cx, cy), (cx, y0 + row_h)], fill=fg, width=lw)
            elif ch.strip():
                font = fc if is_wide(ch) else fl
                # 垂直居中：用 anchor 近似
                d.text((x0, y0 + row_h // 2), ch, font=font, fill=fg, anchor="lm")
            col += 2 if is_wide(ch) else 1
    img.save(out_path, "PNG")
    return out_path, width, height


def find_blocks(paths, min_box=8):
    """找出含足够多制表符的代码块。"""
    out = []
    for f in paths:
        s = open(f, encoding="utf-8").read()
        for m in re.finditer(r"```(\w*)\n(.*?)```", s, flags=re.S):
            body = m.group(2)
            if sum(1 for ch in body if ch in BOX) < min_box:
                continue
            ln = s[: m.start()].count("\n") + 1
            out.append((f, ln, body.rstrip("\n").split("\n")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="assets/diagrams")
    ap.add_argument("--file")
    ap.add_argument("--line", type=int)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    os.chdir(args.root)
    paths = sorted(glob.glob("*/[0-9][0-9]-*.md")) + sorted(glob.glob("*.md"))
    blocks = find_blocks(paths)
    if args.file:
        blocks = [b for b in blocks if b[0].endswith(args.file) and (args.line is None or b[1] == args.line)]
    if args.list:
        for f, ln, lines in blocks:
            print(f"{f} L{ln}  {len(lines)}行  -> {os.path.basename(f)[:6]}-L{ln}.png")
        print(f"共 {len(blocks)} 个")
        return
    os.makedirs(args.out, exist_ok=True)
    for f, ln, lines in blocks:
        base = os.path.basename(f)
        m2 = re.match(r"(\d{2})", base)
        prefix = m2.group(1) if m2 else re.sub(r"[^\w\u4e00-\u9fff]", "", base)[:4] or "blk"
        name = f"{prefix}-L{ln}.png"
        p, w, h = render(lines, os.path.join(args.out, name))
        print(f"OK {p}  {w}x{h}")


if __name__ == "__main__":
    main()
