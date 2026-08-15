# -*- coding: utf-8 -*-
"""v6.0 ⭐ Magic 口令层：精确匹配身份/能力/知识口令 → 固定模板（零 LLM）

用户指示：卷首语/身份模板（"我是 Émile"identity 桶）中的能力词作为 magic keywords
精确匹配——特定口令不走 LLM；模糊变体由 LLM 判断（更上游 route_intent）。
保持 LLM 接口（用户可能换问法）——LLM 判断与口令结合：LLM 在更上游分流。
"""
import re

# Magic 口令：精确/强匹配 → 固定模板（零 LLM）
MAGIC_PATTERNS = [
    # (正则, intent, reason)
    # 身份口令（卷首语）
    (re.compile(r'^(你是谁|你叫什么|你的名字|你是什么|你是谁啊|你叫什么名字|你是什么老师|你是哪位)$'), 'interface', 'magic:identity'),
    # 能力口令（identity 桶：我能帮你做的事）
    (re.compile(r'^(你能做什么|你会做什么|你有什么功能|你能帮我做什么|你有哪些功能|你的功能|你可以做什么|你能干什么|你能帮我做些什么)$'), 'interface', 'magic:capability'),
    # 能力细分（identity 桶能力词精确短语）
    (re.compile(r'^(你能帮我(学知识|做题目|找答案|聊想法|学习|复习|规划|画知识导图|生成文档|记住我)|你能(教|讲|解|出|画|生成|记住).{0,6})$'), 'interface', 'magic:capability_detail'),
    # 知识口令（"你学过什么" → knowledge 库清点）
    (re.compile(r'^(你学过什么|你学过哪些|你学了什么|你懂什么|你掌握什么|你会什么|你了解什么|你的知识库|你有什么知识|你收藏了什么资料|你收着什么资料)$'), 'knowledge', 'magic:knowledge'),
    # 界面/使用口令
    (re.compile(r'^(怎么使用|怎么用|如何使用|操作指南|这个网站怎么用|这个页面怎么用|这个界面怎么用)$'), 'interface', 'magic:usage'),
]


def match_magic(text: str) -> dict:
    """匹配 magic 口令。命中返回 {intent, reason, matched_text}，未命中返回 None。
    仅精确/强匹配（完整句子），不模糊匹配——模糊变体留给 LLM。"""
    t = (text or '').strip()
    if not t:
        return None
    t_clean = re.sub(r'[。？！!?，,、\s]+$', '', t)
    for pattern, intent, reason in MAGIC_PATTERNS:
        if pattern.match(t_clean):
            return {'intent': intent, 'reason': reason, 'matched_text': t_clean}
    return None


if __name__ == '__main__':
    tests = [
        ('你是谁', 'interface', True),
        ('你叫什么名字', 'interface', True),
        ('你是哪位', 'interface', True),
        ('你能做什么', 'interface', True),
        ('你有哪些功能', 'interface', True),
        ('你能帮我学知识', 'interface', True),
        ('你能帮我画知识导图', 'interface', True),
        ('你能帮我记住我', 'interface', True),
        ('你学过什么', 'knowledge', True),
        ('你会什么', 'knowledge', True),
        ('你的知识库', 'knowledge', True),
        ('你收藏了什么资料', 'knowledge', True),
        ('怎么使用', 'interface', True),
        ('你是谁呀', None, False),      # 变体 → LLM
        ('你能做什么呀', None, False),   # 变体 → LLM
        ('帮我分析这段话', None, False), # 复合输入 → 不走 magic
        ('什么是导数', None, False),
        ('今天天气怎么样', None, False),
        ('你好', None, False),          # 问候 → greeting 不走 magic
    ]
    for t, exp_intent, exp_hit in tests:
        r = match_magic(t)
        hit = r is not None
        intent = r['intent'] if r else None
        ok = hit == exp_hit and (intent == exp_intent if hit else True)
        print('%s %-22s hit=%-5s intent=%-10s' % ('✅' if ok else '❌', t, hit, intent))
