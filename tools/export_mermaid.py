#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把全书 81 个 mermaid 代码块导出为 PNG（发布到不支持 Mermaid 渲染的平台时使用）。

依赖：mermaid-cli（npx @mermaid-js/mermaid-cli），首次运行会下载 Chromium；
     本机若被网络策略阻断，请在有外网的机器上执行：
       npm i -g @mermaid-js/mermaid-cli
       python3 tools/export_mermaid.py --render

不渲染时先出清单与 .mmd 源文件：
       python3 tools/export_mermaid.py            # 只导出 .mmd + mapping
       python3 tools/export_mermaid.py --list     # 只看清单
"""
from __future__ import annotations

import argparse
import base64
import glob
import os
import re
import subprocess
import sys
import time
import urllib.request

OUT = "assets/mermaid"
BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)
INK = "https://mermaid.ink/img/"


def render_online(body: str, width: int = 1280) -> bytes:
    """调用 mermaid.ink 渲染。返回 PNG 字节；失败抛异常。

    注意：图定义会以 base64 发送到第三方服务，仅适用于公开内容。
    """
    b64 = base64.urlsafe_b64encode(body.encode("utf-8")).decode()
    url = f"{INK}{b64}?type=png&bgColor=white&width={width}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    if not data.startswith(b"\x89PNG"):
        raise ValueError(f"非 PNG 响应：{data[:80]!r}")
    return data



def collect2():
    """在 collect() 基础上附加「讲内序号」，用于稳定文件名。

    文件名用 {讲号}-{序号} 而非行号：行号会随正文编辑漂移，
    序号只在增删图块时变化，不会因为改一段文字就让全部图失联。
    """
    items = collect()
    cnt = {}
    out = []
    for no, ln, f, body in items:
        cnt[no] = cnt.get(no, 0) + 1
        out.append((no, cnt[no], ln, f, body))
    return out


def collect():
    """返回 [(讲号, 块起始行, 源文件, mermaid文本)]，按全书顺序。

    只收集「顶层」围栏块：被更长围栏（如四反引号 python 块）包住的 ```mermaid
    属于代码示例中的字符串，不是文档里的图，必须排除，否则会渲染出多余的图。
    """
    files = sorted(glob.glob("*/[0-9][0-9]-*.md")) + ["00-全书导读与架构总览.md"]
    files = [f for f in dict.fromkeys(files) if os.path.exists(f)]
    items = []
    for f in files:
        lines = open(f, encoding="utf-8").read().split("\n")
        m = re.match(r"(\d{2})-", os.path.basename(f))
        no = m.group(1) if m else "00"
        i = 0
        while i < len(lines):
            mo = re.match(r"^(`{3,})\s*([\w+-]*)\s*$", lines[i])
            if not mo:
                i += 1
                continue
            fence, lang = len(mo.group(1)), (mo.group(2) or "").lower()
            start = i + 1
            j = i + 1
            while j < len(lines):
                mj = re.match(r"^(`{3,})\s*([\w+-]*)\s*$", lines[j])
                if mj and len(mj.group(1)) >= fence and not (mj.group(2) or ""):
                    break
                j += 1
            if lang == "mermaid":
                items.append((no, start, f, "\n".join(lines[start:j]).rstrip()))
            i = j + 1
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--render", action="store_true", help="调用本地 mmdc 渲染 PNG（需 Chromium）")
    ap.add_argument("--online", action="store_true", help="调用 mermaid.ink 在线渲染，无需本地 Chromium")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--scale", type=str, default="2", help="导出倍率，公众号建议 2x")
    ap.add_argument("--sleep", type=float, default=0.4, help="在线渲染请求间隔（秒），避免限流")
    args = ap.parse_args()

    items = collect()
    print(f"共 {len(items)} 个 mermaid 块")
    if args.list:
        for no, ln, f, body in items:
            head = body.strip().split("\n")[0][:30]
            print(f"  {no}-L{ln:<4} {head}")
        return

    os.makedirs(OUT, exist_ok=True)
    mapping = ["| 文件 | 源位置 | 类型 |", "|---|---|---|"]
    ok = fail = 0
    for i, (no, seq, ln, f, body) in enumerate(collect2(), 1):
        name = f"{no}-{seq:02d}"
        mmd = os.path.join(OUT, f"{name}.mmd")
        png = os.path.join(OUT, f"{name}.png")
        with open(mmd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body + "\n")
        kind = body.strip().split("\n")[0].split()[0]
        mapping.append(f"| {name}.png | {f}:L{ln} | {kind} |")
        if args.render:
            cmd = [
                "npx", "-y", "@mermaid-js/mermaid-cli", "-i", mmd, "-o", png,
                "-w", str(args.width), "-s", args.scale,
                "-b", "white", "--quiet",
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(png):
                ok += 1
            else:
                fail += 1
                print(f"  [FAIL] {name}: {r.stderr.strip().splitlines()[-1][:100] if r.stderr else '?'}")
        elif args.online:
            try:
                data = render_online(body, args.width)
                with open(png, "wb") as fh:
                    fh.write(data)
                ok += 1
                if i % 10 == 0:
                    print(f"  已渲染 {i}/{len(items)}")
            except Exception as e:
                fail += 1
                print(f"  [FAIL] {name}: {type(e).__name__} {str(e)[:80]}")
            time.sleep(args.sleep)
    with open(os.path.join(OUT, "mapping.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Mermaid 图与源位置对照\n\n" + "\n".join(mapping) + "\n")
    print(f"清单已写入 {OUT}/mapping.md")
    if args.render or args.online:
        print(f"渲染完成：成功 {ok}，失败 {fail}")
        sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
