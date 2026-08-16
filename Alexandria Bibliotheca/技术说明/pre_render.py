# -*- coding: utf-8 -*-
"""
pre_render.py — 图册预渲染器（Oracle 重新设计方案 · 第二阶段）

职责：
1. 读 figures/manifest.json（extract_figures 产物）
2. 逐图用 Playwright 打开独立 HTML → mermaid.js 渲染 → 提取 SVG outerHTML
3. 写入 figures/fig_N.svg；失败立即报错（不静默跳过）

关键点：
- 等 `.mermaid svg` 出现 **且** 内部 text 节点 getBBox() 非空（中文字体加载完成）
- 每图独立页面 → 渲染相互隔离，单图失败不连坐
- 输出 SVG 供 build_html 以 <img> 嵌入 → 源码物理上不进最终 HTML

用法：
    python pre_render.py [figures_dir]
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

ASSETS = os.path.dirname(os.path.abspath(__file__))  # 交付物/文档模板（含 mermaid.min.js）
MERMAID_JS = os.path.join(ASSETS, "mermaid.min.js")


def figure_html(code: str) -> str:
    """单图独立 HTML：mermaid.min.js 内联（避开 file:// 本地资源拦截）+ 中文字体回退。"""
    with io.open(MERMAID_JS, encoding="utf-8", errors="replace") as fh:
        mermaid_js = fh.read()
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
    body {{ margin: 0; padding: 0; }}
    /* 中文字体回退：保证 SVG text 节点有正确字体度量 */
    @font-face {{
        font-family: 'CJK-Fallback';
        src: local('Microsoft YaHei'), local('SimHei'), local('Noto Sans CJK SC');
    }}
    .mermaid {{ font-family: 'CJK-Fallback', 'trebuchet ms', verdana, arial; }}
</style>
</head>
<body>
<pre class="mermaid">{code}</pre>
<script>
{mermaid_js}
</script>
<script>
    mermaid.initialize({{ startOnLoad: true, securityLevel: 'loose', theme: 'dark' }});
</script>
</body>
</html>"""


def render_svg(page, code: str, svg_path: str) -> None:
    """渲染单图 → 提取 SVG → 写文件。等待 text.getBBox() 非空（字体就绪）。"""
    page.set_content(figure_html(code), wait_until="load")
    # 等待 SVG 出现且文本节点有尺寸（中文字体加载完成）
    page.wait_for_function(
        """() => {
            const svg = document.querySelector('.mermaid svg');
            if (!svg) return false;
            const texts = svg.querySelectorAll('text');
            if (texts.length === 0) return true;  // 无文本的图直接算完成
            return Array.from(texts).some(t => {
                try { const b = t.getBBox(); return b.width > 0 && b.height > 0; }
                catch (e) { return false; }
            });
        }""",
        timeout=15000,
    )
    page.wait_for_timeout(300)  # 稳定
    svg = page.locator(".mermaid svg").first.evaluate("el => el.outerHTML")
    with io.open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(svg)


def main():
    figures_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(ASSETS), "figures")
    manifest_path = os.path.join(figures_dir, "manifest.json")
    manifest = json.load(io.open(manifest_path, encoding="utf-8"))
    figs = manifest["figures"]

    ok, fail = 0, []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        for f in figs:
            svg_path = os.path.join(figures_dir, f["svg"])
            try:
                render_svg(page, f["code"], svg_path)
                size = os.path.getsize(svg_path)
                ok += 1
                print(f"  ✅ 图 {f['num']}: {svg_path} ({size//1024} KB)")
            except Exception as e:
                fail.append((f["num"], f["title"], str(e)[:100]))
                print(f"  ❌ 图 {f['num']}: {f['title'][:20]} 渲染失败 → {str(e)[:80]}")
        browser.close()

    print(f"\n预渲染完成: {ok}/{len(figs)} 成功")
    if fail:
        print("失败清单:")
        for num, title, err in fail:
            print(f"  图 {num} ({title[:20]}): {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
