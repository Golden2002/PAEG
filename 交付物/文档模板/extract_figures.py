# -*- coding: utf-8 -*-
"""
extract_figures.py — 图册解析器（Oracle 重新设计方案 · 第一阶段）

职责：
1. 从 PAEG技术说明.md 严格提取全部 mermaid 图（标题 + ```mermaid 代码块紧邻）
2. 幽灵块检测：裸 `mermaid` 行（缺 ``` 前缀）→ 立即中止并报行号
3. 生成 figures/manifest.json（图号/标题/源码/文件名 → 真值源）

用法：
    python extract_figures.py <md_path> [figures_dir]

输出：
    figures/manifest.json —— 供 pre_render / verify_atlas 使用
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 严格匹配：**图 N · 标题** 后（可含表格/说明文字）取最近的一个 ```mermaid ... ``` 代码块
# group1=图号(1-27/2B)  group2=标题  group3=mermaid源码
FIG_RE = re.compile(
    r'\*\*图\s+([0-9A-Za-z]+)\s*·\s*([^*\n]+?)\*\*'
    r'(?:(?!\*\*图\s)[\s\S])*?'          # 非贪婪：跳过表格/说明（但不越过下一个图标题）
    r'```mermaid\n(.*?)```',
    re.S,
)
# 幽灵块：不在代码 fence 内的裸 mermaid 行（图册残渣检测）
GHOST_RE = re.compile(r'^\s*mermaid\s*$', re.M)


def extract(md_path: str) -> list:
    """提取全部图 → list[dict]；幽灵块/数量异常直接抛错。"""
    md = io.open(md_path, encoding="utf-8").read()

    # 1) 幽灵块检测：裸 mermaid 行（缺 ```mermaid 前缀）
    ghosts = []
    for m in GHOST_RE.finditer(md):
        line_no = md[: m.start()].count("\n") + 1
        ghosts.append(line_no)
    if ghosts:
        raise SystemExit(
            f"FATAL: 检测到 {len(ghosts)} 个幽灵块（裸 mermaid 行，缺 ```mermaid 前缀）"
            f"—— 第 {ghosts} 行。这是此前泄漏的根因，必须先修复文档！"
        )

    # 2) 严格提取
    figs = []
    seen = set()
    for m in FIG_RE.finditer(md):
        num, title, code = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if num in seen:
            raise SystemExit(f"FATAL: 图号重复: 图 {num}（{title}）——文档存在重复块！")
        seen.add(num)
        figs.append({
            "num": num,
            "title": title,
            "code": code,
            "svg": f"fig_{num}.svg",
            "mmd": f"fig_{num}.mmd",
        })

    # 3) 数量断言（当前文档 28 图）
    if len(figs) != 28:
        raise SystemExit(
            f"FATAL: 提取到 {len(figs)} 张图（期望 28）——严格正则可能漏块或文档结构变化！"
        )
    return figs


def write_manifest(figs: list, figures_dir: str) -> dict:
    """生成 manifest.json + 每图 .mmd 源码副本。"""
    os.makedirs(figures_dir, exist_ok=True)
    for f in figs:
        mmd = os.path.join(figures_dir, f["mmd"])
        with io.open(mmd, "w", encoding="utf-8") as fh:
            fh.write(f["code"] + "\n")
    manifest = {
        "version": "1.1.8",
        "count": len(figs),
        "figures": figs,
    }
    mp = os.path.join(figures_dir, "manifest.json")
    with io.open(mp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest


def main():
    if len(sys.argv) < 2:
        print("用法: python extract_figures.py <md_path> [figures_dir]")
        sys.exit(1)
    md_path = os.path.abspath(sys.argv[1])
    figures_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(md_path), "figures")
    figs = extract(md_path)
    manifest = write_manifest(figs, figures_dir)
    print(f"✅ 提取 {manifest['count']} 张图，幽灵块 0")
    print(f"   manifest → {os.path.join(figures_dir, 'manifest.json')}")
    for f in figs:
        print(f"   图 {f['num']}: {f['title'][:30]}")


if __name__ == "__main__":
    main()
