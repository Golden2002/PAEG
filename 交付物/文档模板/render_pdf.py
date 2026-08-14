# -*- coding: utf-8 -*-
"""render_pdf.py — 把 Markdown 技术文档渲染成专业 PDF（可复用模板）。
v0.70+ 用 Playwright（系统 Edge channel）渲染——可靠等待 Mermaid 图渲染完成。
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
        <div class="item"><span class="k">Version</span><span class="v">v0.70<small>正式交付版</small></span></div>
        <div class="item"><span class="k">Document</span><span class="v">技术白皮书<small>Technical Brief</small></span></div>
        <div class="item"><span class="k">Date</span><span class="v">2026 · 08<small>项目所有者内部</small></span></div>
        <div class="item"><span class="k">Status</span><span class="v">READY<small>可用</small></span></div>
'''


def _mermaid_sub(m):
    return '<pre class="mermaid">' + m.group(1) + '</pre>'


def build_html(md_path: str, title: str = None, sub: str = None,
               tagline: str = None, features: str = None, meta: str = None) -> str:
    """md → 完整 HTML（占位符替换 + Mermaid 块处理）"""
    tpl = io.open(os.path.join(ASSETS, 'template.html'), encoding='utf-8').read()
    md_text = io.open(md_path, encoding='utf-8').read()
    # Mermaid 块 → <pre class="mermaid">（非 raw 正则——匹配换行）
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
    """Playwright（系统 Edge channel）渲染 PDF，等待 Mermaid 渲染完成"""
    final = build_html(md_path, title=title, sub=sub)
    tmp_html = os.path.join(ASSETS, '_render_tmp.html')
    io.open(tmp_html, 'w', encoding='utf-8').write(final)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('需安装 playwright：pip install playwright')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='msedge')
        page = browser.new_page(device_scale_factor=2)  # v0.70+ 高清截图（2x）
        page.goto('file:///' + tmp_html.replace('\\', '/'), wait_until='networkidle')
        # 等待 Mermaid 渲染完成（关键：等所有 .mermaid 变 svg）
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('.mermaid').length > 0 && "
                "Array.from(document.querySelectorAll('.mermaid')).every(el => el.querySelector('svg') !== null)",
                timeout=30000)
        except Exception as _me:
            print(f'[render] Mermaid 等待超时/部分: {_me}')
        # v0.70+ 修复：Chromium 打印 Mermaid SVG 空白——用 Playwright 元素截图把每个 svg 存为 PNG
        #（PNG 打印 100% 稳定），再把 HTML 中 .mermaid 替换为 <img src="...png">
        try:
            page.wait_for_timeout(2000)  # 等 mermaid 渲染稳定
            svg_count = page.locator('.mermaid svg').count()
            print(f'[render] Mermaid SVG 数量: {svg_count}')
            for i in range(svg_count):
                loc = page.locator('.mermaid svg').nth(i)
                png_path = os.path.join(ASSETS, f'_mermaid_{i}.png')
                loc.screenshot(path=png_path)
            # 替换 HTML 中的 .mermaid 为 img
            page.evaluate("""(count) => {
                const pres = document.querySelectorAll('.mermaid');
                pres.forEach((pre, i) => {
                    if (i < count) {
                        const img = document.createElement('img');
                        img.src = '_mermaid_' + i + '.png';
                        img.style.display = 'block';
                        img.style.margin = '8mm auto';          /* v0.70+ 图与文字间距 */
                        img.style.maxWidth = '100%';
                        img.style.maxHeight = '170mm';          /* v0.70+ 限高防跨页截断 */
                        img.style.objectFit = 'contain';
                        img.style.pageBreakInside = 'avoid';    /* 不跨页断开 */
                        img.style.breakInside = 'avoid';
                        pre.replaceWith(img);
                    }
                });
            }""", svg_count)
            page.wait_for_timeout(500)
        except Exception as _se:
            print(f'[render] Mermaid 转 PNG 跳过: {_se}')
        # v0.70 修复：用独立标准页面（dsf=1）输出 PDF——device_scale_factor=2 会导致
        # page.pdf 的 CSS px 物理缩放异常（封面 1122px 只渲染上半 47%）
        # 先把已替换 Mermaid→PNG 的最终 HTML 落盘，供 dsf=1 页面加载
        tmp_html2 = os.path.join(ASSETS, '_render_tmp2.html')
        try:
            final_html = page.content()
            io.open(tmp_html2, 'w', encoding='utf-8').write(final_html)
        except Exception as _e2:
            print(f'[render] HTML 快照失败: {_e2}')
            tmp_html2 = tmp_html
        pdf_page = browser.new_page(device_scale_factor=1)
        pdf_page.goto('file:///' + tmp_html2.replace('\\', '/'), wait_until='networkidle')
        pdf_page.wait_for_timeout(500)
        pdf_page.pdf(path=out_pdf, format='A4', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        pdf_page.close()
        if os.path.exists(tmp_html2) and tmp_html2 != tmp_html:
            try:
                os.remove(tmp_html2)
            except Exception:
                pass

        browser.close()
    os.remove(tmp_html)
    return os.path.getsize(out_pdf)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Markdown → 专业 PDF')
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--title', default=None)
    ap.add_argument('--sub', default=None)
    args = ap.parse_args()
    size = render(args.input, args.output, title=args.title, sub=args.sub)
    print(f'PDF 生成: {args.output} ({size} B)')
