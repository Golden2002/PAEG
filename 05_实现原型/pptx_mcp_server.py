# -*- coding: utf-8 -*-
"""生成 PPT MCP server（v0.25 ⭐）
PAEG 通过 MCP 调用本 server 的 generate_ppt 工具：
- 输入：主题 + 来源（用户文档/知识库检索结果/对话历史摘要）
- 输出：生成 .pptx 到 downloads/，返回文件路径
依赖：python-pptx（已装 1.0.2）
"""
import sys, io, os, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 允许的最小 python-pptx
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads', 'ppt')

# 品牌配色（与 PAEG 一致）
C_PRIMARY = RGBColor(0x1F, 0x4E, 0x79)
C_ACCENT = RGBColor(0x2E, 0x75, 0xB6)
C_LIGHT = RGBColor(0xDE, 0xEB, 0xF7)
C_DARK = RGBColor(0x22, 0x22, 0x22)
C_GRAY = RGBColor(0x66, 0x66, 0x66)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_ORANGE = RGBColor(0xC5, 0x5A, 0x11)


def _parse_outline(text: str) -> list:
    """把 LLM/文本大纲解析为 [{title, points:[...], notes}]"""
    slides = []
    lines = [l.strip() for l in (text or '').splitlines() if l.strip()]
    cur = None
    for ln in lines:
        # 匹配 "## 标题" 或 "1. 标题" 或 "- 标题" 作为页标题
        m = re.match(r'^(#{1,4})\s+(.+)$', ln)
        if m:
            if cur: slides.append(cur)
            cur = {'title': m.group(2).strip(), 'points': [], 'notes': ''}
            continue
        m = re.match(r'^(\d+)[.、)]\s*(.+)$', ln)
        if m:
            if cur: slides.append(cur)
            cur = {'title': m.group(2).strip(), 'points': [], 'notes': ''}
            continue
        m = re.match(r'^[-*•]\s*(.+)$', ln)
        if m:
            if cur:
                cur['points'].append(m.group(1).strip())
            else:
                cur = {'title': '要点', 'points': [m.group(1).strip()], 'notes': ''}
            continue
        # 普通行：作为要点或备注
        if cur:
            if ln.startswith('备注') or ln.startswith('note'):
                cur['notes'] = ln.split(':', 1)[-1].strip()
            else:
                cur['points'].append(ln)
    if cur: slides.append(cur)
    return slides or [{'title': '演示文稿', 'points': ['（空大纲，请补充内容）'], 'notes': ''}]


def _set_text(shape, text, size=18, bold=False, color=C_DARK, align=PP_ALIGN.LEFT):
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = 'Microsoft YaHei'
    p.alignment = align
    return shape


def _add_title_bar(slide, title):
    """顶部品牌色标题条"""
    bar = slide.shapes.add_shape(1, 0, 0, Inches(13.33), Inches(1.0))  # rectangle
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_PRIMARY
    bar.line.fill.background()
    tf = bar.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = C_WHITE
    p.font.name = 'Microsoft YaHei'
    p.alignment = PP_ALIGN.LEFT
    return bar


def _add_bullets(slide, points, left, top, width, height):
    from pptx.util import Inches as In
    box = slide.shapes.add_textbox(In(left), In(top), In(width), In(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, pt in enumerate(points[:6]):  # 每页最多 6 条
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = ('• ' if not pt.startswith('•') else '') + pt
        p.font.size = Pt(16)
        p.font.color.rgb = C_DARK
        p.font.name = 'Microsoft YaHei'
        p.space_after = Pt(8)
    return box


def _extract_material_text(uid: str, max_files: int = 3, max_chars: int = 8000) -> str:
    """v0.26 ⭐ 需求D：从用户上传物料（Library/usr_knowledge/<uid>/）提取文字。

    支持 md/txt（直接读）、pdf（pypdf 抽文本）、docx（python-docx 抽段落）。
    路径安全：只允许 uid 对应目录，拒绝路径穿越。失败静默返回 ""。
    """
    try:
        import os as _os
        _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _root = _os.path.join(_proj, 'Library', 'usr_knowledge')
        _udir = _os.path.join(_root, str(uid))
        # 路径安全：realpath 后必须在 root 下
        _real_root = _os.path.realpath(_root)
        _real_udir = _os.path.realpath(_udir)
        if not _real_udir.startswith(_real_root) or '/' in str(uid) or '\\' in str(uid):
            return ""
        if not _os.path.isdir(_real_udir):
            return ""
        _texts = []
        for _f in sorted(_os.listdir(_real_udir))[:max_files]:
            _fp = _os.path.join(_real_udir, _f)
            if not _os.path.isfile(_fp):
                continue
            _ext = _os.path.splitext(_f)[1].lower()
            try:
                if _ext in ('.md', '.txt'):
                    with open(_fp, encoding='utf-8', errors='ignore') as fh:
                        _texts.append(f"【{_f}】\n{fh.read()[:3000]}")
                elif _ext == '.pdf':
                    try:
                        from pypdf import PdfReader
                        _rd = PdfReader(_fp)
                        _txt = "\n".join(p.extract_text() or "" for p in _rd.pages[:5])
                        _texts.append(f"【{_f}】\n{_txt[:3000]}")
                    except Exception:
                        pass
                elif _ext == '.docx':
                    try:
                        import docx as _docx
                        _doc = _docx.Document(_fp)
                        _txt = "\n".join(p.text for p in _doc.paragraphs[:60])
                        _texts.append(f"【{_f}】\n{_txt[:3000]}")
                    except Exception:
                        pass
            except Exception:
                continue
        _joined = "\n\n".join(_texts)
        return _joined[:max_chars]
    except Exception:
        return ""


def generate_ppt(topic: str, outline: str = "", sources: str = "",
                 out_name: str = "", uid: str = "") -> dict:
    """生成演示文稿 .pptx。

    Args:
        topic: 演示主题（如"语言学导论"）
        outline: 大纲文本（LLM 生成的 ## 标题 + 要点）
        sources: 来源说明（用户文档/知识库/对话历史，写入备注页）
        out_name: 输出文件名（不含扩展名，默认按主题+时间戳）
        uid: v0.26 ⭐ 用户 id——若提供，自动从 Library/usr_knowledge/<uid>/
             提取用户上传物料（md/pdf/docx 文字+图片说明）作为内容补充

    Returns:
        {"ok": bool, "path": str, "slides": int, "error": str}
    """
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        slides_data = _parse_outline(outline or topic)
        if not slides_data:
            slides_data = [{'title': topic, 'points': [], 'notes': ''}]
        # v0.26 ⭐ 需求D：用户物料提取——有 uid 时补充物料文字到首页/备注
        material = ""
        if uid:
            material = _extract_material_text(uid)
        if material and slides_data:
            _first = slides_data[0]
            _extra = [m[:120] for m in material.split("\n") if m.strip()][:6]
            if _extra:
                _first.setdefault('points', []).extend(
                    f"(物料) {e}" for e in _extra[:3])
                _first['notes'] = (_first.get('notes') or '') + \
                    f"\n\n用户物料摘要：{material[:600]}"
        # 首屏 + 内容页
        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)
        blank = prs.slide_layouts[6]  # blank

        # 封面页
        s = prs.slides.add_slide(blank)
        bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid(); bg.fill.fore_color.rgb = C_PRIMARY
        bg.line.fill.background()
        _set_text(s.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11), Inches(1.6)),
                  topic, size=40, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
        _set_text(s.shapes.add_textbox(Inches(1.2), Inches(4.0), Inches(11), Inches(1.0)),
                  'PAEG · Émile 演示文稿', size=18, color=C_LIGHT, align=PP_ALIGN.CENTER)
        if sources:
            _set_text(s.shapes.add_textbox(Inches(1.5), Inches(5.6), Inches(10.3), Inches(1.2)),
                      f'资料来源：{sources[:120]}', size=12, color=C_LIGHT, align=PP_ALIGN.CENTER)
        elif material:
            _set_text(s.shapes.add_textbox(Inches(1.5), Inches(5.6), Inches(10.3), Inches(1.2)),
                      '内容基于用户上传的资料整理', size=12, color=C_LIGHT, align=PP_ALIGN.CENTER)

        # 内容页
        for i, sd in enumerate(slides_data[:20]):  # 最多 20 页
            s = prs.slides.add_slide(blank)
            _add_title_bar(s, sd['title'])
            pts = sd['points'] or ['（本页要点）']
            _add_bullets(s, pts, 0.6, 1.4, 12.1, 5.2)
            # 页码
            _set_text(s.shapes.add_textbox(Inches(12.2), Inches(7.0), Inches(1.0), Inches(0.4)),
                      f'{i+2}', size=10, color=C_GRAY, align=PP_ALIGN.RIGHT)
            if sd.get('notes'):
                s.notes_slide.notes_text_frame.text = sd['notes']

        fname = (out_name or f'{re.sub(r"[^\w\u4e00-\u9fff]+", "_", topic)[:30]}_{os.path.getmtime(__file__):.0f}') + '.pptx'
        fname = re.sub(r'[\\/:*?"<>|]', '_', fname)
        path = os.path.join(OUT_DIR, fname)
        prs.save(path)
        return {"ok": True, "path": path, "slides": len(slides_data) + 1, "error": ""}
    except Exception as e:
        return {"ok": False, "path": "", "slides": 0, "error": str(e)}


# ─── FastMCP server 暴露 ───
try:
    from fastmcp import FastMCP
    mcp = FastMCP("paeg-pptx")

    @mcp.tool()
    def generate_presentation(topic: str, outline: str = "", sources: str = "",
                              out_name: str = "", uid: str = "") -> dict:
        """根据主题+大纲+来源生成演示文稿 PPT（PAEG 教育智能体调用）。
        大纲格式：每页以 '## 标题' 或 '1. 标题' 开头，要点以 '- ' 开头。
        uid（可选）：用户 id——提供时自动提取该用户上传物料（md/pdf/docx）的文字补充内容。"""
        return generate_ppt(topic, outline, sources, out_name, uid)

    if __name__ == "__main__":
        mcp.run(transport="stdio")
except Exception as e:
    mcp = None
    if __name__ == "__main__":
        print(f'FastMCP 不可用: {e}；直接函数测试:')
        r = generate_ppt('语言学导论', '## 什么是语言学\n- 研究语言的科学', '用户文档')
        print(r)

