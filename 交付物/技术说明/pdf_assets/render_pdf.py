# -*- coding: utf-8 -*-
"""render_pdf.py — 把 Markdown 技术文档渲染成专业 PDF（可复用模板）。
用法：python render_pdf.py input.md output.pdf [--title 文档标题] [--sub 副标题]
依赖：python-markdown + Edge/Chromium（--headless --print-to-pdf）
"""
import argparse
import io
import os
import subprocess
import sys
import tempfile

import markdown

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)))
EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]

DEFAULT_TAGLINE = (
    '多 Agent 架构 · 35 学科 × 4 学段 · 自我进化闭环<br>'
    'PAEG — 让每个学生拥有一位会思考、会调整、会成长的老师'
)
DEFAULT_FEATURES = '''
        <div class="f" data-num="35"><span class="f-k">35</span><span class="f-v">学科 × 4 学段</span></div>
        <div class="f" data-num="25"><span class="f-k">25</span><span class="f-v">MCP 工具</span></div>
        <div class="f" data-num="09"><span class="f-k">9</span><span class="f-v">领域专家 subagent</span></div>
        <div class="f" data-num="G11"><span class="f-k">G1-G11</span><span class="f-v">自我进化闭环</span></div>
'''
DEFAULT_META = '''
        <div class="item"><span class="k">Version</span><span class="v">v0.70<small>正式交付版</small></span></div>
        <div class="item"><span class="k">Document</span><span class="v">技术白皮书<small>Technical Brief</small></span></div>
        <div class="item"><span class="k">Date</span><span class="v">2026 · 08<small>项目所有者内部</small></span></div>
        <div class="item"><span class="k">Status</span><span class="v">READY<small>可用</small></span></div>
'''


def find_browser():
    for c in EDGE_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


def render(md_path: str, out_pdf: str, title: str = None, sub: str = None,
           tagline: str = None, features: str = None, meta: str = None):
    """md → HTML（套模板占位符）→ Edge headless → PDF"""
    tpl = io.open(os.path.join(ASSETS, 'template.html'), encoding='utf-8').read()
    md_text = io.open(md_path, encoding='utf-8').read()
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

    tmp_html = os.path.join(ASSETS, '_render_tmp.html')
    io.open(tmp_html, 'w', encoding='utf-8').write(final)

    browser = find_browser()
    if not browser:
        raise RuntimeError('未找到 Edge/Chrome')
    subprocess.run([browser, '--headless', '--disable-gpu',
                    '--print-to-pdf=' + out_pdf, '--no-margins',
                    'file:///' + tmp_html.replace('\\', '/')],
                   capture_output=True, timeout=120)
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
