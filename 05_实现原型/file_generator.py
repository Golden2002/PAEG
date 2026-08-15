"""
PAEG 文件生成器（v0.12）

任务2：让智能体生成可下载的文件（练习题 / 文章 / 讲义）。
- 用真实 LLM 生成内容
- 格式化为规范的 Markdown 文件
- 支持下载

用法：
    from file_generator import FileGenerator
    fg = FileGenerator(llm)
    content, filename = fg.generate_quiz(learner, subject, topic, n_questions=5)
    fg.save(content, filename)  # 存到 downloads/ 目录
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

from subagents import _safe_chat


def _safe_filename(name: str) -> str:
    """净化文件名：去除非法字符，限制长度。"""
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name[:40] or 'unnamed'


class FileGenerator:
    """文件生成器：练习题 / 文章 / 讲义。"""

    def __init__(self, llm, download_dir: Optional[str] = None):
        self.llm = llm
        base = os.path.dirname(os.path.abspath(__file__))
        self.download_dir = download_dir or os.path.join(base, 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)

    def generate_quiz(self, learner, subject: str, topic: str,
                      n_questions: int = 5) -> tuple:
        """生成练习题（含答案与解析）。

        返回 (markdown_content, filename)
        """
        grade = getattr(learner, 'grade_level', 'high_school')
        grade_cn = {'high_school': '高中', 'undergraduate': '本科',
                    'graduate_exam': '考研', 'middle_school': '初中'}.get(grade, grade)
        desc = getattr(learner, 'self_description', '') or ''

        system = (
            "你是一位严谨、朴素的命题老师（薇依式的：题目准确、不花哨、有思考价值）。\n"
            "请设计一份练习，要求：\n"
            "1. 题目由浅入深，从基础到有挑战\n"
            "2. 每题附答案和简短解析（解析要讲清'为什么'，不要只给答案）\n"
            "3. 语言朴素准确，不使用'让我们一起'等空洞话\n"
            "4. 题目要有真实思考价值，不只是机械计算\n"
        )
        user = (
            f"教学对象：{grade_cn}学生。学科：{subject}。主题：{topic}。\n"
            f"题目数量：{n_questions}。\n"
            + (f"学生情况：{desc}\n" if desc else "")
            + "输出格式：\n"
            f"# {subject} - {topic} 练习题\n\n"
            "## 一、基础题\n1. ...\n\n## 二、进阶题\n...\n\n## 参考答案与解析\n"
        )
        content = _safe_chat(self.llm, system, user, max_tokens=1200)
        if not content:
            content = f"# {subject} - {topic} 练习题\n\n（生成失败，请重试）\n"

        filename = f"练习题_{_safe_filename(subject)}_{_safe_filename(topic)}_{datetime.now().strftime('%Y%m%d%H%M')}.md"
        return content, filename

    def generate_article(self, learner, subject: str, topic: str,
                         length: str = 'medium') -> tuple:
        """生成一篇讲解文章（讲义/科普文）。

        length: short(~300字) / medium(~600字) / long(~1000字)
        """
        grade = getattr(learner, 'grade_level', 'high_school')
        grade_cn = {'high_school': '高中', 'undergraduate': '本科',
                    'graduate_exam': '考研', 'middle_school': '初中'}.get(grade, grade)
        desc = getattr(learner, 'self_description', '') or ''
        len_guide = {'short': '约 300 字', 'medium': '约 600 字', 'long': '约 1000 字'}.get(length, '约 600 字')

        system = (
            "你是一位朴素、有力量的写作者（薇依式的语言：准确、具体、不浮夸、不卖弄）。\n"
            "请写一篇讲解文章，要求：\n"
            "1. 语言朴素平实，像一位认真的老师在娓娓道来\n"
            "2. 禁止'让我们踏上/开启'等空洞套话，禁止语气词堆砌\n"
            "3. 结构清晰：引入（一个问题或现象）→ 核心讲解 → 举例 → 小结\n"
            "4. 用准确的动词和名词，不硬造'拉一拉'类奇怪动词短语\n"
            f"5. 长度：{len_guide}\n"
        )
        user = (
            f"读者：{grade_cn}学生。学科：{subject}。主题：{topic}。\n"
            + (f"读者情况：{desc}\n" if desc else "")
            + "直接输出文章正文，不要额外说明。"
        )
        content = _safe_chat(self.llm, system, user, max_tokens=1000)
        if not content:
            content = f"# {topic}\n\n（生成失败，请重试）\n"

        filename = f"文章_{_safe_filename(subject)}_{_safe_filename(topic)}_{datetime.now().strftime('%Y%m%d%H%M')}.md"
        return content, filename

    # v0.66 ⭐ 完整教学讲义（Oracle 设计：6 段教学过程，用户核心需求）
    def generate_handout(self, learner, subject: str, topic: str,
                         outline: Optional[str] = None,
                         length: str = "medium") -> tuple:
        """生成完整教学讲义（markdown，授课式完整教学过程）。

        Args:
            learner: 学生画像（学段/风格/薄弱点，注入针对性）
            subject/topic: 学科与主题
            outline: 可选——已存在大纲（有则按大纲扩展，否则 LLM 自构）
            length: short(~800字) / medium(~1500字) / long(~2500字)
        Returns:
            (markdown_content, filename, structured_dict)
        """
        grade = getattr(learner, 'grade_level', 'high_school')
        grade_cn = {'high_school': '高中', 'undergraduate': '本科',
                    'graduate_exam': '考研', 'middle_school': '初中'}.get(grade, grade)
        desc = getattr(learner, 'self_description', '') or ''
        style = getattr(learner, 'cognitive_style', '') or ''
        len_guide = {'short': '约 800 字', 'medium': '约 1500 字',
                     'long': '约 2500 字'}.get(length, '约 1500 字')

        system = (
            f"你是{grade_cn}{subject}老师，正在为一名{grade_cn}学生写一份**完整教学讲义**。\n\n"
            "【硬性结构】（必须严格按以下 6 段输出，缺一不可）：\n"
            "1. 教学目标（知识/能力/素养目标）\n"
            "2. 导入（一个具体情境或提问，联系旧知或生活，必须有'过桥句'过渡到新课）\n"
            "3. 新课讲授（分 3.1/3.2/3.3 小节，每节含：定义 + 直觉解释 + 例子 + 例题带解）\n"
            "4. 巩固练习（2-3 题由浅入深，每题附答案与解析——解析讲清'为什么'而非只给答案）\n"
            "5. 课堂小结（3-5 条核心要点 + 文字版知识结构）\n"
            "6. 作业与拓展（课后练习 2 题 + 拓展思考 1 题 + 学习方法提示）\n\n"
            "【语言要求】\n"
            "- 像真人老师在写教案/讲义：朴素、准确、有温度\n"
            "- 公式用 $...$ 包裹，不堆砌术语\n"
            "- 定义后必须跟直觉解释（不跳步）\n"
            f"- 长度：{len_guide}\n\n"
            "【语言风格（L1 规范，必须内化）】\n"
            "- 说具体的话，不说空话；句子短，一句一个意思\n"
            "- 不用生僻词、翻译腔、公文腔\n"
            "- 避免 AI 腔：不用'首先/其次/最后'三段式、不用'总之'总结句、"
            "不用破折号堆砌\n"
            "- 用准确的名词承担重量，不用形容词堆感受\n\n"
            "【禁止】\n"
            "- 不要'讲解文章'式平铺直叙（缺导入/小结/作业）\n"
            "- 不要只给定义不给例子\n"
            "- 不要只列练习题不给解析\n\n"
            "【输出】纯 markdown，标题层级清晰（# 主题，# 一级段，### 小节）。"
        )
        user = (
            f"学生：{grade_cn}，{('学习风格：' + style + '。') if style else ''}"
            f"（学科：{subject}，主题：{topic}）\n"
            + (f"学生情况：{desc}\n" if desc else "")
            + (f"参考大纲：\n{outline}\n" if outline else "")
        )
        # v0.66 ⭐ 统一资源门面：讲义基于 KB/用户物料/网络事实（不凭空写）
        try:
            from services.library import collect_all_resources
            _res = collect_all_resources(
                str(getattr(learner, "id", "") or ""), topic, llm=self.llm,
                subject=subject, include_web=False)
            if _res.get("has_any"):
                user += "\n\n【可用资料（讲义应基于这些事实）】\n" + _res["block"] + "\n"
        except Exception:
            pass
        user += "请输出完整教学讲义。"
        content = _safe_chat(self.llm, system, user, max_tokens=2000)
        # v0.66 ⭐ L0+L2 语言规范：讲义全文过语言守门（AI 味/省略句/动宾搭配修正）
        try:
            from services.lang_gate import lang_gate_content
            content = lang_gate_content(content, context=f"handout:{subject}-{topic}")
        except Exception:
            pass
        if not content or len(content.strip()) < 100:
            # 兜底：结构化模板（保证 6 段存在）
            content = (
                f"# {topic} 讲义\n\n"
                f"> 学习对象：{grade_cn}{subject} 学生\n\n"
                f"## 一、教学目标\n- 知识目标：理解 {topic} 的核心概念\n"
                f"- 能力目标：能应用 {topic} 解决基础问题\n"
                f"- 素养目标：建立对 {subject} 的学习兴趣\n\n"
                f"## 二、导入\n**情境**：请先想一想，你在生活中哪里会遇到 {topic}？\n"
                f"**过渡**：带着这个问题，我们正式学习 {topic}。\n\n"
                f"## 三、新课讲授\n### 3.1 {topic} 的定义\n"
                f"- 定义：{topic} 是{subject}中的一个重要概念。\n"
                f"- 直觉解释：（此处应补充直觉理解）\n"
                f"- 例题：（此处应补充例题与解）\n\n"
                f"## 四、巩固练习\n1. **基础**：…（答案：… 解析：…）\n"
                f"2. **进阶**：…（答案：… 解析：…）\n\n"
                f"## 五、课堂小结\n- 核心要点 1\n- 核心要点 2\n\n"
                f"## 六、作业与拓展\n- 课后练习\n- 拓展思考\n"
            )

        # 结构化返回（供下游讲稿/PPT/视频复用）
        structured = {
            "content": content,
            "filename": f"讲义_{_safe_filename(subject)}_{_safe_filename(topic)}_{datetime.now().strftime('%Y%m%d%H%M')}.md",
            "sections": _parse_handout_sections(content),
        }
        return content, structured["filename"], structured

    def save(self, content: str, filename: str) -> str:
        """把内容保存到 downloads/ 目录，返回文件路径。"""
        path = os.path.join(self.download_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    # v0.18：把任意回答/讲解保存为文档（Markdown + HTML 双格式）
    def save_answer(self, content: str, title: str,
                    subject: str = "通用") -> tuple:
        """把一段回答保存为可下载文档。

        返回 (md_path, html_path)
        - Markdown：保留原始格式（公式/列表）
        - HTML：带基础样式，可直接打开/打印/分享
        """
        ts = datetime.now().strftime('%Y%m%d%H%M')
        safe_title = _safe_filename(title)
        md_filename = f"{safe_title}_{ts}.md"
        html_filename = f"{safe_title}_{ts}.html"

        md_path = self.save(content, md_filename)

        # 简单 HTML 包装（转义 + 保留换行）
        import html as _html
        esc = _html.escape(content)
        # 公式占位保留（MathJax 渲染）
        body = esc.replace('\n\n', '</p><p>').replace('\n', '<br>')
        html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{_html.escape(title)}</title>
<script>
window.MathJax = {{ tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }} }};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
<style>
  body {{ font-family: 'Songti SC', 'SimSun', serif; max-width: 780px; margin: 40px auto; padding: 0 24px; line-height: 1.8; color: #222; }}
  h1 {{ font-size: 22px; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
  h2 {{ font-size: 18px; margin-top: 24px; }}
  p {{ margin: 12px 0; }}
  blockquote {{ border-left: 3px solid #ccc; margin-left: 0; padding-left: 16px; color: #555; }}
  code {{ background: #f5f5f5; padding: 1px 5px; border-radius: 3px; }}
  pre {{ background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  table {{ border-collapse: collapse; }}
  td, th {{ border: 1px solid #ddd; padding: 6px 10px; }}
  .footer {{ margin-top: 40px; color: #999; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<h1>{_html.escape(title)}</h1>
<p>{body}</p>
<div class="footer">由 PAEG · Émile Novis 生成 · {subject}</div>
</body>
</html>"""
        with open(os.path.join(self.download_dir, html_filename), 'w', encoding='utf-8') as f:
            f.write(html_doc)
        return md_path, os.path.join(self.download_dir, html_filename)

    def list_files(self) -> list:
        """列出已生成的文件。"""
        if not os.path.exists(self.download_dir):
            return []
        return sorted(
            [{'name': f, 'path': os.path.join(self.download_dir, f),
              'size': os.path.getsize(os.path.join(self.download_dir, f))}
             for f in os.listdir(self.download_dir)],
            key=lambda x: -x['size']
        )[:50]

def _parse_handout_sections(md: str) -> list:
    """从讲义 markdown 解析 6 段结构（供下游讲稿/PPT/视频复用）。"""
    import re as _re
    sections = []
    cur = None
    for line in md.split('\n'):
        s = line.strip()
        m = _re.match(r'^(#{2,3})\s+(.+)', s)
        if m and ('目标' in m.group(2) or '导入' in m.group(2) or '新课' in m.group(2)
                  or '练习' in m.group(2) or '小结' in m.group(2) or '作业' in m.group(2)
                  or '拓展' in m.group(2)):
            if cur:
                sections.append(cur)
            cur = {'title': m.group(2), 'body': [], 'subsections': []}
        elif m and cur and m.group(1) == '###':
            cur['subsections'].append({'title': m.group(2), 'body': []})
            cur['subsections'][-1]['_active'] = True
            if len(cur['subsections']) > 1:
                cur['subsections'][-2]['_active'] = False
        elif s and cur:
            if cur.get('subsections') and cur['subsections'][-1].get('_active'):
                cur['subsections'][-1]['body'].append(s)
            else:
                cur['body'].append(s)
    if cur:
        sections.append(cur)
    for sec in sections:
        for sub in sec.get('subsections', []):
            sub.pop('_active', None)
    return sections
