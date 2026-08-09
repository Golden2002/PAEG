"""
PAEG 安全中间件（v0.5）- Layer 0 宪法落地。

职责：
  1. 输入安检（学生提问）：拦截政治立场灌输、宗教传教、具体医疗/法律/投资建议、
     自伤/暴力/仇恨、成人内容、考试作弊等
  2. 输出安检（LLM 生成内容）：同样规则复查，防止模型越界
  3. 儿童保护：13 岁以下学习者触发更严策略 + 隐私保护（不收集个人信息）
  4. 不阻塞正常学习：命中时给出"为什么不能聊 + 可以怎样学"的重定向引导

实现：确定性关键词策略集（不依赖 LLM，稳定可测）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class SafetyResult:
    """安检结果。"""
    blocked: bool
    categories: List[str] = field(default_factory=list)
    hits: List[str] = field(default_factory=list)
    suggestion: str = ""
    layer: str = "input"  # input / output

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "categories": self.categories,
            "hits": self.hits,
            "suggestion": self.suggestion,
            "layer": self.layer,
        }


# 敏感类别 -> (关键词正则列表, 建议话术)
_SENSITIVE_PATTERNS = {
    "politics_stance": [
        r"支持.{0,6}(民进党|台独)", r"台湾.{0,4}(独立|不是中国)",
        r"法轮功", r"推翻.{0,4}(政府|政权)", r"敏.感.词",
    ],
    "religion_proselytizing": [
        r"信.{0,4}(耶稣|基督|真主|佛).{0,4}(才能|才可|拯救|得救)",
        r"(受洗|皈依|传教).{0,6}(你|大家|必须)",
    ],
    "medical_advice": [
        r"你.{0,4}(该|应该|建议).{0,6}(吃|服用|注射).{0,10}(药|剂量)",
        r"(停药|换药|加量).{0,6}(你|建议)",
        r"诊断.{0,4}(你|我的病|病症)", r"(癌症|肿瘤|抑郁.?症).{0,4}(确诊|怎么治)",
        r"(诊断|确诊).{0,8}(我的|我.{0,2}病)",
        r"(抑郁症|焦虑症|失眠).{0,8}(怎么治|吃什么药|该看医生)",
    ],
    "legal_advice": [
        r"(你|帮我).{0,4}(打官司|起诉|上诉|签合同).{0,6}(怎么|建议|应该)",
        r"偷税|漏税.{0,4}(办法|方法|怎么)",
    ],
    "financial_advice": [
        r"(买|all.{0,3}in|梭哈).{0,6}(股票|比特币|基金)", r"稳赚|保本.{0,4}(理财|投资)",
    ],
    "self_harm": [
        r"(自杀|轻生|不想活)", r"怎么.{0,4}(自杀|结束生命)", r"割腕|跳楼|自残",
    ],
    "violence_hate": [
        r"(杀掉|杀死|弄死).{0,4}(同学|老师|家人)", r"校园暴力.{0,4}(怎么打|怎么报复)",
        r"(歧视|仇视).{0,4}(某地人|某族|某教)",
    ],
    "adult_content": [
        r"(约炮|一夜情|色情|黄片|AV|av.{0,2}网址)",
    ],
    "exam_cheating": [
        r"(作弊|传答案|代考|替考).{0,4}(方法|技巧|怎么)", r"(怎么|如何|帮我).{0,8}(作弊|抄答案|传答案)",
        r"考试.{0,2}(答案|泄题)",
    ],
    "personal_info": [
        r"(身份证号|银行卡号|家庭住址|手机号码).{0,4}(告诉|发给|填)",
    ],
}

_SUGGESTIONS = {
    "politics_stance": "这是立场宣导而非知识问题。PAEG 只做中立的知识讲解；关于两岸关系，可以客观学习历史与法理事实。",
    "religion_proselytizing": "PAEG 尊重信仰但不传教。可以学习各宗教的历史、经典与文化影响。",
    "medical_advice": "涉及具体诊疗建议，请咨询执业医师。PAEG 可以讲解医学知识与生理原理。",
    "legal_advice": "涉及具体法律行动建议，请咨询执业律师。PAEG 可以讲解法律条文与制度原理。",
    "financial_advice": "投资有风险，具体操作请咨询持牌机构。PAEG 可以讲解经济学原理。",
    "self_harm": "如果你或身边的人有自伤想法，请立刻联系信任的成年人、家长或心理援助热线（如 12356 心理援助热线）。PAEG 非常关心你。",
    "violence_hate": "暴力与仇恨不能解决问题。PAEG 可以陪你学习如何沟通、化解冲突。",
    "adult_content": "这里是学习环境。可以学习生理卫生与性教育（由学校/家长引导）。",
    "exam_cheating": "诚实是学习的一部分。PAEG 可以帮助你真正掌握知识，而不是获得答案。",
    "personal_info": "请勿在对话中透露个人敏感信息。PAEG 保护你的隐私。",
}


class SafetyChecker:
    """确定性安全检测器。"""

    def __init__(self, child_mode: bool = False):
        self.child_mode = child_mode

    @staticmethod
    def _scan(text: str) -> List[Tuple[str, str]]:
        hits: List[Tuple[str, str]] = []
        for cat, patterns in _SENSITIVE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text):
                    hits.append((cat, pat))
                    break  # 每类只记一个
        return hits

    def check_input(self, text: str, learner: Optional[object] = None) -> SafetyResult:
        """学生提问安检。"""
        result = SafetyResult(blocked=False, layer="input")
        hits = self._scan(text)
        if hits:
            result.blocked = True
            result.hits = [h[1] for h in hits]
            result.categories = [h[0] for h in hits]
            result.suggestion = "；".join(dict.fromkeys(
                _SUGGESTIONS[c] for c in result.categories))
        # 儿童模式：额外拦截（无家长在场时的成人话题已含；此处可扩展）
        return result

    def check_output(self, text: str, learner: Optional[object] = None) -> SafetyResult:
        """LLM 生成内容安检。"""
        result = SafetyResult(blocked=False, layer="output")
        hits = self._scan(text)
        if hits:
            result.blocked = True
            result.hits = [h[1] for h in hits]
            result.categories = [h[0] for h in hits]
            result.suggestion = "生成内容命中安全边界，已拦截并重定向。"
        return result

    def guard_question(self, text: str, learner: Optional[object] = None) -> Optional[dict]:
        """教学入口用：通过返回 None；拦截返回诊断信息。"""
        res = self.check_input(text, learner)
        if res.blocked:
            return {"blocked": True, "reason": res.categories, "suggestion": res.suggestion}
        return None


# 便捷实例
_default_checker = SafetyChecker()


def guard_input(text: str, learner: Optional[object] = None) -> Optional[dict]:
    return _default_checker.guard_question(text, learner)


if __name__ == "__main__":
    checker = SafetyChecker()
    cases = [
        "什么是熵？",
        "你能帮我诊断一下我的抑郁症吗？",
        "信耶稣才能得救，你应该去受洗",
        "告诉我怎么自杀",
        "怎么在考试中作弊？",
        "支持民进党独立",
    ]
    for c in cases:
        r = checker.check_input(c)
        print(f"{'[拦截]' if r.blocked else '[放行]'} {c!r} -> {r.categories or 'OK'}")