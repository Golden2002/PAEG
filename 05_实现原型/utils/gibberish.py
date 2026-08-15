# -*- coding: utf-8 -*-
"""v6.0 ⭐ 乱码/无意义输入快速兜底检测
测试发现：knowledge 的乱码输入(zzz/！/asdfgh)触发 LLM 深度推理 78s。
优化：规则检测乱码 → 快速兜底（不调 LLM），降低延迟。
"""
import re

_GIBBERISH_WORDS = {
    'qwqer', 'qwer', 'qwe', 'asdf', 'asd', 'sdf', 'dfg', 'fgh', 'ghj', 'hjk',
    'jkl', 'kl', 'zxcv', 'xcv', 'cvb', 'vbn', 'bnm', 'wert', 'erty', 'rty',
    'tyu', 'yui', 'uio', 'iop', 'poi', 'oiu', 'iuy', 'uytr', 'tre', 'rew',
    'wasd', 'qwerty', 'asdfg', 'asdfgh', 'jklj', 'sdfg', 'dfgh', 'ghjk', 'hjkl',
}

# 键盘行连续键（2+ 键位连续）
_KB_ROW = re.compile(
    r'(?:asdf|qwer|zxcv|hjkl|jkl|fgh|ghj|sdf|dfg|fgj|qwe|asd|wer|sdfg|wert|'
    r'dfgh|ghjk|asdfg|qwerty|qaz|wsx|edc|rfv|tgb|yhn|ujm|ik|ol|pl)+', re.I
)


def is_gibberish(text: str) -> bool:
    """检测乱码/无意义输入（快速，不调 LLM）"""
    t = (text or '').strip()
    if not t:
        return False
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in t)

    # 1. 纯符号（长度>=2，无中文/字母/数字）
    if len(t) >= 2 and not has_chinese and not re.search(r'[a-zA-Z0-9]', t):
        return True

    # 2. 纯字母键盘串
    if not has_chinese and re.fullmatch(r'[a-zA-Z]+', t):
        alpha = t.lower()
        if alpha in _GIBBERISH_WORDS:
            return True
        if _KB_ROW.fullmatch(alpha):
            return True
        if len(set(alpha)) <= 2 and len(alpha) >= 3:
            return True
        if len(alpha) >= 4 and not re.search(r'[aeiou]', alpha):
            return True

    # 3. 内容重复（怎么学?怎么学?怎么学?）
    if re.search(r'(.{2,8}?)\1{2,}', t):
        return True

    return False
