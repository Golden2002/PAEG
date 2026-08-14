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
        <div class="item"><span class="k">Version</span><span class="v">v0.71<small>排版优化版</small></span></div>
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
        page = browser.new_page(device_scale_factor=1)  # v0.71: dsf=1 截图——2x 使 PNG 高 2 倍产生超长窄图+空白
        page.goto('file:///' + tmp_html.replace('\\', '/'), wait_until='networkidle')
        # 等待 Mermaid 渲染完成（关键：等所有 .mermaid 变 svg）
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('.mermaid').length > 0 && "
                "Array.from(document.querySelectorAll('.mermaid')).every(el => el.querySelector('svg') !== null)",
                timeout=30000)
        except Exception as _me:
            print(f'[render] Mermaid 等待超时/部分: {_me}')
        # v0.71: Chromium 打印 Mermaid SVG 空白——元素截图 PNG 嵌入（100% 稳定）
        # 截图 dsf=1（避免 2x 产生超长窄图）；包装为 <figure class="mermaid-fig"> 由 CSS 统一缩放
        try:
            page.wait_for_timeout(2000)  # 等 mermaid 渲染稳定
            svg_count = page.locator('.mermaid svg').count()
            print(f'[render] Mermaid SVG 数量: {svg_count}')
            # v0.71 ⭐ 修复：部分 Mermaid SVG 自带深色背景（rgb 31,41,55）——
            # 截图前 JS 强制每个 svg 白底（CSS 选择器未覆盖 svg 自身 background）
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('.mermaid svg').forEach(s => {
                        s.style.setProperty('background', '#ffffff', 'important');
                        s.style.setProperty('background-color', '#ffffff', 'important');
                    });
                }""")
                page.wait_for_timeout(200)
            except Exception:
                pass
            for i in range(svg_count):
                loc = page.locator('.mermaid svg').nth(i)
                png_path = os.path.join(ASSETS, f'_mermaid_{i}.png')
                loc.screenshot(path=png_path)
            # v0.71 Oracle+visual 双咨询：按 PNG 真实宽高比分类（wide/tall/normal/hero），
            #   CSS 三类缩放——wide 占满版心+min-height 防孤；tall 限高 240mm+居中；normal 等比例不溢出
            _cls_map = {}
            try:
                from PIL import Image as _PILImage
                # 读 md 的 mermaid 块（判断 sequenceDiagram——天然横向不按 ar 分类）
                import re as _re
                _md_text = io.open(md_path, encoding="utf-8").read()
                _blocks = _re.findall(r"```mermaid\n(.*?)```", _md_text, _re.S)
                for i in range(svg_count):
                    png_path = os.path.join(ASSETS, f'_mermaid_{i}.png')
                    with _PILImage.open(png_path) as _im:
                        _w, _h = _im.size
                    _ar = _w / _h if _h else 1.0
                    # v0.71: sequenceDiagram 天然横向，一律 normal（占满版心宽）；
                    # flowchart 按宽高比分类 wide/tall/normal/hero
                    _is_seq = bool(_blocks) and i < len(_blocks) and "sequenceDiagram" in _blocks[i]
                    if _is_seq:
                        _cls = "normal"
                    elif _ar >= 3.0:
                        _cls = "wide"
                    elif _ar <= 0.6:
                        _cls = "tall"
                    elif 0.8 <= _ar <= 1.3 and i in (0, 8):  # 关键架构总览图独占页放大
                        _cls = "hero"
                    elif _ar > 1.6:
                        _cls = "tall"
                    else:
                        _cls = "normal"
                    _cls_map[i] = _cls
                print(f'[render] 图分类: {_cls_map}')
            except Exception as _ce:
                print(f'[render] 图分类失败(全部 normal): {_ce}')
                _cls_map = {i: "normal" for i in range(svg_count)}
            # 替换 HTML 中的 .mermaid 为 <figure class="mermaid-fig XXX"><img>
            # Playwright evaluate 只接受 1 个 arg——用对象 {count, clsMap, sizes}
            # v0.71: 显式 img width/height 属性（PNG 实际尺寸）——修复 Chromium print 动态 img 高度塌陷（491x6）
            _sizes = {}
            try:
                from PIL import Image as _PILImage2
                for i in range(svg_count):
                    png_path = os.path.join(ASSETS, f'_mermaid_{i}.png')
                    with _PILImage2.open(png_path) as _im:
                        _sizes[i] = _im.size
            except Exception:
                _sizes = {i: (0, 0) for i in range(svg_count)}
            page.evaluate("""(payload) => {
                const pres = document.querySelectorAll('.mermaid');
                pres.forEach((pre, i) => {
                    if (i < payload.count) {
                        const fig = document.createElement('figure');
                        fig.className = 'mermaid-fig ' + (payload.clsMap[String(i)] || 'normal');
                        const img = document.createElement('img');
                        img.src = '_mermaid_' + i + '.png';
                        img.alt = '架构示意图 ' + (i + 1);
                        const sz = payload.sizes[String(i)];
                        if (sz && sz[0] > 0) {
                            img.width = sz[0];   // 显式 intrinsic 尺寸——print 不塌陷
                            img.height = sz[1];
                        }
                        fig.appendChild(img);
                        pre.replaceWith(fig);
                    }
                });
            }""", {"count": svg_count, "clsMap": {str(k): v for k, v in _cls_map.items()},
                   "sizes": {str(k): v for k, v in _sizes.items()}})
            page.wait_for_timeout(500)
        except Exception as _se:
            print(f'[render] Mermaid 转 PNG 跳过: {_se}')
        # v0.71: 独立标准页面（dsf=1）输出 PDF
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
