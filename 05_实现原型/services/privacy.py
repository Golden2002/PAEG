# -*- coding: utf-8 -*-
"""services/privacy.py —— §3.79 C5 ⭐ PII 字段级脱敏（家长/教师视图合规深化）

memo/013 教育特有合规："PII/学生数据：加密 + 本地化 + 可导出删除"。
本模块提供字段级脱敏（mask_pii），供家长视图等对外暴露面使用：

  - 中国大陆手机号（11 位，1[3-9] 开头）→ 138****8000
  - 邮箱 → a***@domain
  - 18 位身份证号 → 前 4 后 4
  - 长数字串（银行卡/QQ 等 ≥8 位）→ 前后各 4

原则：只读文本处理（无状态），防御式（异常原样返回），可测试。
"""
from __future__ import annotations

import re

_MOBILE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
_EMAIL = re.compile(r"([A-Za-z0-9._%+-]{1,4})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_IDCARD = re.compile(r"(?<!\d)(\d{4})\d{10}(\d{4})(?!\d)")
_LONGNUM = re.compile(r"(?<!\d)(\d{8,})(?!\d)")


def mask_pii(text: str) -> str:
    """字段级 PII 脱敏（手机号/邮箱/身份证/长数字串）。

    Args:
        text: 原始文本（可能含 PII）

    Returns:
        脱敏后文本；异常/非 str 原样返回。
    """
    if not isinstance(text, str) or not text:
        return text
    try:
        _t = _MOBILE.sub(r"\1****\3", text)
        _t = _EMAIL.sub(r"\1***\2", _t)
        _t = _IDCARD.sub(r"\1**********\2", _t)
        _t = _LONGNUM.sub(lambda m: m.group(1)[:4] + "****" + m.group(1)[-4:], _t)
        return _t
    except Exception:
        return text


__all__ = ["mask_pii"]
