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
