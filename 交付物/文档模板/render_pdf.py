# -*- coding: utf-8 -*-
"""render_pdf.py — Markdown → 专业 PDF（v1.1 ⭐ SVG 矢量直出终极版）

v1.1 架构：Mermaid 块保留为 <pre class="mermaid">，浏览器端 mermaid.js 渲染为
SVG 矢量图，直接 page.pdf 输出——**不截图 PNG**（矢量无限清晰，无截图/深色/
白框/压扁/截断问题）。图主题由 markdown 内 %%{init:{theme}}%% 逐图控制。

用法：python render_pdf.py input.md output.pdf [--title 文档标题]
依赖：python-markdown + playwright（channel=msedge 用系统 Edge）
"""
import argparse
import io
import os
import re
import sys

import markdown

ASSETS = os.path.dirname(os.path.abspath(__file__))

DEFAULT_TAGLINE = (
    '多 Agent 架构 · 35 学科 × 4 学段 · 自我进化闭环<br>'
    'PAEG — 让每个学生拥有一位会思考、会调整、会成长的老师'
)
DEFAULT_FEATURES = '''
        <div class="f" data-num="35"><span class="f-k">35</span><span class="f-v">学科 × 4 学段</span></div>
        <div class="f" data-num="54"><span class="f-k">54</span><span class="f-v">工具（含 MCP/skills）</span></div>
        <div class="f" data-num="09"><span class="f-k">9</span><span class="f-v">领域专家 subagent</span></div>
        <div class="f" data-num="G11"><span class="f-k">G1-G11</span><span class="f-v">自我进化闭环</span></div>
'''
DEFAULT_META = '''
        <div class="item"><span class="k">Version</span><span class="v">v1.1<small>SVG矢量直出版</small></span></div>
        <div class="item"><span class="k">Document</span><span class="v">技术白皮书<small>Technical Brief</small></span></div>
        <div class="item"><span class="k">Date</span><span class="v">2026 · 08<small>项目所有者内部</small></span></div>
        <div class="item"><span class="k">Status</span><span class="v">READY<small>可用</small></span></div>
'''


def _mermaid_sub(m):
    """Mermaid 块 → <pre class="mermaid">（保留给浏览器端 mermaid.js 渲染 SVG）
    v1.1.9 ⭐ 泄漏根因修复：此前"图26 泄漏"实为文档混入的幽灵块（缺 ```mermaid 前缀的
    残留副本，build_html 正则匹配不到 → 纯文本进 HTML → print 原样输出）。
    幽灵块已从 md 删除，恢复纯 SVG 直出（28 图全 SVG）。"""
    return '<pre class="mermaid">' + m.group(1) + '</pre>'


def build_html(md_path: str, title: str = None, sub: str = None,
               tagline: str = None, features: str = None, meta: str = None) -> str:
    """md → 完整 HTML（占位符替换 + Mermaid 块保留为 pre.mermaid）"""
    tpl = io.open(os.path.join(ASSETS, 'template.html'), encoding='utf-8').read()
    md_text = io.open(md_path, encoding='utf-8').read()
    md_text = re.sub('```mermaid\n(.*?)```', _mermaid_sub, md_text, flags=re.S)
    content_html = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
    repl = {
        '{{DOC_TITLE}}': title or 'PAEG 教育智能体技术说明',
        '{{BRAND_TEXT}}': 'EDUCATION · AGENT · WHITEPAPER',
        '{{TAGLINE_LINES}}': tagline or DEFAULT_TAGLINE,
        '{{TITLE_LINE_1}}': '教育智能体',
        '{{TITLE_LINE_2}}': '技术说明',
        '{{SUBTITLE}}': sub or '面向教育场景的智能教学代理：架构、能力矩阵与工程实现',
        '{{FEATURES}}': features or DEFAULT_FEATURES,
        '{{META_ITEMS}}': meta or DEFAULT_META,
        '{{FOOTER_LEFT}}': 'EDU · AGENT',
        '{{FOOTER_RIGHT}}': 'Confidential — Internal Use Only',
        '{{CONTENT}}': content_html,
    }
    final = tpl
    for k, v in repl.items():
        final = final.replace(k, v)
    return final


def render(md_path: str, out_pdf: str, title: str = None, sub: str = None) -> int:
    """v1.1 SVG 矢量直出：浏览器渲染 mermaid → SVG 矢量 → page.pdf"""
    final = build_html(md_path, title=title, sub=sub)
    tmp_html = os.path.join(ASSETS, '_render_tmp.html')
    io.open(tmp_html, 'w', encoding='utf-8').write(final)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('需安装 playwright：pip install playwright')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='msedge')
        page = browser.new_page()
        page.goto('file:///' + tmp_html.replace('\\', '/'), wait_until='networkidle')
        # 等待 Mermaid 全部渲染为 SVG（关键）
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('.mermaid').length > 0 && "
                "Array.from(document.querySelectorAll('.mermaid')).every(el => el.querySelector('svg') !== null)",
                timeout=30000)
        except Exception as _me:
            print(f'[render] Mermaid 等待超时/部分: {_me}')
        page.wait_for_timeout(2000)  # 等字体/渲染稳定
        svg_count = page.locator('.mermaid svg').count()
        print(f'[render] Mermaid SVG 数量: {svg_count}（SVG 矢量直出）')
        # v1.1.1 ⭐ 大图强制分页 + 白框防御（用户要求：大图直接分页，标题+图独占一页）
        try:
            page.evaluate("""() => {
                /* 白框防御：SVG 文字关闭 Chromium PDF 的 paint-order 白衬底 */
                document.querySelectorAll('.mermaid svg text, .mermaid svg tspan').forEach(t => {
                    t.style.setProperty('paint-order', 'stroke fill markers', 'important');
                    t.style.setProperty('stroke', 'transparent', 'important');
                });
                /* 大图分页：SVG 高度 > 页高 55% → 在【图标题段落】前插分页符（标题+图独占一页）。
                   用 svg.viewBox 高度（真实图高，不含 margin）判断 */
                const pageH = window.innerHeight;
                document.querySelectorAll('pre.mermaid').forEach(pre => {
                    const svg = pre.querySelector('svg');
                    if (!svg) return;
                    const vb = svg.viewBox && svg.viewBox.baseVal;
                    const svgH = vb && vb.height ? vb.height : svg.getBoundingClientRect().height;
                    if (svgH > pageH * 0.55) {
                        /* 找到 pre 前面的标题段落（含"图 N"）——分页符插在标题前 */
                        let anchor = pre;
                        let prev = anchor.previousElementSibling;
                        if (prev && prev.tagName === 'P' && /图\s*\d/.test(prev.textContent)) {
                            anchor = prev;
                        }
                        const before = anchor.previousElementSibling;
                        if (!before || !before.classList.contains('page-break-spacer')) {
                            const spacer = document.createElement('div');
                            spacer.className = 'page-break-spacer';
                            spacer.style.cssText = 'page-break-before:always;break-before:page;height:1px;';
                            anchor.parentNode.insertBefore(spacer, anchor);
                        }
                    }
                });
            }""")
            page.wait_for_timeout(200)
        except Exception as _pe:
            print(f'[render] 大图分页/白框处理跳过: {_pe}')
        # 直接输出 PDF——SVG 矢量保留，图无限清晰
        page.pdf(path=out_pdf, format='A4', print_background=True,
                 margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        browser.close()
    os.remove(tmp_html)
    return os.path.getsize(out_pdf)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Markdown → 专业 PDF (SVG 矢量直出)')
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--title', default=None)
    ap.add_argument('--sub', default=None)
    args = ap.parse_args()
    size = render(args.input, args.output, title=args.title, sub=args.sub)
    print(f'PDF 生成: {args.output} ({size} B)')
