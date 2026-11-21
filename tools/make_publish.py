#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「发布版」文档：把源 Markdown 里的 mermaid 块替换为 PNG 图片引用，
供不支持 Mermaid 的平台（公众号 / 知乎 / 掘金富文本）直接粘贴使用。

源文档一律不动——Mermaid 在 GitHub / VS Code / Typora / Notion 下原生渲染，
可编辑、可 diff、可搜索；图片只应出现在发布产物里，避免双维护。

用法：
    python3 tools/make_publish.py            # 全部生成到 publish/
    python3 tools/make_publish.py --file 01-知识库构建/01-项目概览与数据准备.md
    python3 tools/make_publish.py --list     # 只看哪些讲缺图

依赖：assets/mermaid/*.png（tools/export_mermaid.py --online 生成）
      assets/diagrams/*.png（tools/render_ascii.py 生成）
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from export_mermaid import collect2 as collect_mermaid  # noqa: E402
from render_ascii import BOX, find_blocks  # noqa: E402

MD_FILES = [
    f for f in sorted(glob.glob("*/[0-9][0-9]-*.md")) + ["00-全书导读与架构总览.md"]
    if not f.startswith("publish/") and os.path.exists(f)
]


def _relpath_in_publish(target: str, src: str) -> str:
    """target 相对「publish 下该篇所在目录」的路径。

    输出目录是 publish/<源文件目录>/，与源文件所在的仓库位置不同，
    因此不能直接用源文件目录做基准，否则 publish 根下的导读会指向 publish/assets/（死链）。
    """
    base = os.path.join("publish", os.path.dirname(src)) or "publish"
    return os.path.relpath(target, base)


def _exists_in_publish(rel: str, src: str) -> bool:
    base = os.path.join("publish", os.path.dirname(src)) or "publish"
    return os.path.exists(os.path.normpath(os.path.join(base, rel)))


def make_map_mermaid2():
    """(源文件, 起始行) -> png 相对路径（相对 publish/<dir>/）"""
    m = {}
    for no, seq, ln, f, _body in collect_mermaid():
        m[(f, ln)] = _relpath_in_publish(f"assets/mermaid/{no}-{seq:02d}.png", f)
    return m


def make_map_ascii():
    m = {}
    for f, ln, _lines in find_blocks(MD_FILES, min_box=8):
        base = os.path.basename(f)
        mm = re.match(r"(\d{2})", base)
        prefix = mm.group(1) if mm else re.sub(r"[^\w\u4e00-\u9fff]", "", base)[:4] or "blk"
        m[(f, ln)] = _relpath_in_publish(f"assets/diagrams/{prefix}-L{ln}.png", f)
    return m


def process(src, map_mm, map_asc):
    lines = open(src, encoding="utf-8").read().split("\n")
    out, i, n_mm, n_asc, missing = [], 0, 0, 0, []
    while i < len(lines):
        mo = re.match(r"^(`{3,})\s*([\w+-]*)\s*$", lines[i])
        if not mo:
            out.append(lines[i]); i += 1; continue
        fence, lang = mo.group(1), (mo.group(2) or "").lower()
        start = i + 1
        j = i + 1
        while j < len(lines) and not re.match(r"^`{" + str(len(fence)) + r",}\s*$", lines[j]):
            j += 1
        body = "\n".join(lines[start:j])
        if lang == "mermaid":
            key = (src, start)
            png = map_mm.get(key)
            if png and _exists_in_publish(png, src):
                out.append(f"![图 {start}]({png})")
                n_mm += 1
            else:
                missing.append(("mermaid", start))
                out.append(lines[i]); out.extend(lines[start:j])
                if j < len(lines):
                    out.append(lines[j])
            i = j + 1
            continue
        if sum(1 for ch in body if ch in BOX) >= 8:
            key = (src, start)
            png = map_asc.get(key)
            if png and _exists_in_publish(png, src):
                out.append(f"![图 {start}]({png})")
                n_asc += 1
                i = j + 1
                continue
        # 普通代码块：原样保留开围栏、正文和闭合围栏。
        # 早期版本此处只写了 out.extend(lines[start:j]) 就跳到 j+1，
        # 闭合围栏被吞掉，导致发布版代码块永不合闭、后半篇全被渲染成代码。
        out.append(lines[i]); out.extend(lines[start:j])
        if j < len(lines):
            out.append(lines[j])
        i = j + 1
    return "\n".join(out), n_mm, n_asc, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    map_mm, map_asc = make_map_mermaid2(), make_map_ascii()
    files = [f for f in MD_FILES if os.path.exists(f)]
    if args.file:
        files = [f for f in files if f == args.file or f.endswith(args.file)]

    if args.list:
        for src in files:
            _t, _a, _b, missing = process(src, map_mm, map_asc)
            if missing:
                print(f"  [缺图] {src}: {missing}")
        return

    total_mm = total_asc = 0
    for src in files:
        text, n_mm, n_asc, missing = process(src, map_mm, map_asc)
        dst = os.path.join("publish", src)
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        open(dst, "w", encoding="utf-8", newline="\n").write(text)
        total_mm += n_mm; total_asc += n_asc
        tag = f" mermaid×{n_mm} ascii×{n_asc}" + (f" 缺图{len(missing)}" if missing else "")
        print(f"  {src} -> {dst}{tag}")
    print(f"\n共 {len(files)} 篇 | mermaid {total_mm} | ascii {total_asc} -> publish/")


if __name__ == "__main__":
    main()
