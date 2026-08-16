# -*- coding: utf-8 -*-
"""
verify_atlas.py — 图册质量门（Oracle 重新设计方案 · 质量保障）

在 pre_render 之后、PDF 生成之后各跑一次，断言：
1. manifest 计数 == 28（与 extract_figures 一致）
2. 每个 SVG 文件存在且非空（>1KB）
3. SVG 是合法矢量（含 <svg 标签）
4. PDF 文本扫描：禁止出现 mermaid 源码泄漏关键词
   （flowchart/sequenceDiagram/stateDiagram/%%{init/graph TD —— 但排除正文合法引用）

用法：
    python verify_atlas.py <pdf_path> [figures_dir]

退出码：0=通过，1=失败（打印具体违规项）
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# mermaid 源码泄漏关键词（出现在 PDF 文本中即视为泄漏——正文引用会带书名号/引号或中文语境，
# 而裸源码关键字几乎不可能出现在正常排版文本里）
LEAK_KEYWORDS = [
    "%%{init", "flowchart LR", "flowchart TB", "flowchart TD",
    "sequenceDiagram", "stateDiagram", "graph TD", "graph LR",
    "participant ", "subgraph ",
]
# 正文可能合法出现的引用（白名单前缀，匹配到这些不算泄漏）
SAFE_CONTEXT = ["图示", "Mermaid", "mermaid", "图册", "图 1", "§", "README"]


def verify_svgs(figures_dir: str, manifest: dict) -> list:
    """SVG 完整性检查 → 违规列表（空=通过）。"""
    issues = []
    if manifest["count"] != 28:
        issues.append(f"manifest 计数 {manifest['count']} != 28")
    for f in manifest["figures"]:
        p = os.path.join(figures_dir, f["svg"])
        if not os.path.exists(p):
            issues.append(f"缺少 SVG: {f['svg']}")
            continue
        size = os.path.getsize(p)
        if size < 1024:
            issues.append(f"SVG 过小({size}B): {f['svg']}")
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            head = fh.read(200)
        if "<svg" not in head:
            issues.append(f"非法 SVG(无<svg标签): {f['svg']}")
    return issues


def verify_pdf(pdf_path: str) -> list:
    """PDF 泄漏扫描 → 违规列表（空=通过）。"""
    issues = []
    try:
        import fitz  # PyMuPDF
    except ImportError:
        issues.append("未安装 PyMuPDF，跳过 PDF 泄漏扫描")
        return issues
    doc = fitz.open(pdf_path)
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        for kw in LEAK_KEYWORDS:
            idx = text.find(kw)
            if idx >= 0:
                # 上下文检查：若命中位置前 20 字符含安全上下文 → 跳过（正文引用）
                ctx = text[max(0, idx - 20): idx]
                if any(s in ctx for s in SAFE_CONTEXT):
                    continue
                issues.append(f"P{pno+1}: 泄漏关键词 '{kw.strip()}' @...{text[max(0,idx-15):idx+25]!r}...")
    return issues


def main():
    if len(sys.argv) < 2:
        print("用法: python verify_atlas.py <pdf_path> [figures_dir]")
        sys.exit(1)
    pdf_path = os.path.abspath(sys.argv[1])
    figures_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(pdf_path), "figures")

    print("=== 图册质量门 ===")
    issues = []
    # 1. manifest + SVG
    mp = os.path.join(figures_dir, "manifest.json")
    if not os.path.exists(mp):
        issues.append(f"缺少 manifest.json: {mp}（先跑 extract_figures.py）")
    else:
        manifest = json.load(io.open(mp, encoding="utf-8"))
        issues += verify_svgs(figures_dir, manifest)
        print(f"  SVG 检查: manifest {manifest['count']} 图")
    # 2. PDF 泄漏扫描
    if os.path.exists(pdf_path):
        issues += verify_pdf(pdf_path)
        print(f"  PDF 泄漏扫描: {pdf_path}")
    else:
        issues.append(f"PDF 不存在: {pdf_path}")

    if issues:
        print("\n❌ 质量门未通过:")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    print("✅ 质量门全通过：28 图 SVG 完整 + PDF 零泄漏")


if __name__ == "__main__":
    main()
