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


# ---------------------------------------------------------------------------
# v0.37 ⭐ RiskClassifier：情绪支持风险分级（Oracle 方案 C）
# - 6 级：none/distress/passive_ideation/active_ideation/plan_or_means/imminent
# - LLM 优先 + 关键词兜底（个人项目无标注数据，关键词毫秒级先行，LLM 复核取高）
# - 完全不破坏 SafetyChecker（新增独立类，向后兼容）
# ---------------------------------------------------------------------------
import json as _json
from datetime import datetime, timedelta
from pathlib import Path as _Path


class RiskClassifier:
    """6 级风险分级器（关键词确定性分级；LLM 复核由调用方决定是否启用）。

    规则表：memory/RiskRules.json（levels + patterns + opt_out 策略）。
    """

    def __init__(self, rules_path: Optional[str] = None):
        self._rules = self._load_rules(rules_path)
        self._patterns = self._rules.get("patterns", {})
        self._levels = {lvl["level"]: lvl for lvl in self._rules.get("levels", [])}
        self._opt = self._rules.get("opt_out", {})

    @staticmethod
    def _load_rules(rules_path: Optional[str]) -> dict:
        default = _Path(__file__).parent / "memory" / "RiskRules.json"
        path = _Path(rules_path) if rules_path else default
        try:
            return _json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"levels": [], "patterns": {}, "opt_out": {}}

    def classify(self, text: str) -> int:
        """关键词分级（0-5）。调用方如需 LLM 复核，取 max(关键词, LLM) 保守。"""
        text = str(text or "")
        if not text:
            return 0
        # 从高到低检查（imminent > plan > active > passive > distress）
        for level in (5, 4, 3, 2, 1):
            lvl_info = self._levels.get(level)
            if not lvl_info:
                continue
            name = lvl_info["name"]
            patterns = self._patterns.get(name, [])
            for pat in patterns:
                try:
                    if re.search(pat, text):
                        return level
                except re.error:
                    continue
        return 0

    def opt_out_suppressible(self, level: int) -> bool:
        """该级别是否可被 opt_out 压制。"""
        lvl_info = self._levels.get(level, {})
        return bool(lvl_info.get("opt_out_suppressible", False))

    def should_show_resources(self, level: int, opt_out_state: Optional[dict] = None) -> bool:
        """是否必须显示热线/资源。level>=3 强制；level<=2 看 opt_out。"""
        if level >= self._opt.get("force_levels_min", 3):
            return True
        if not opt_out_state or not opt_out_state.get("active"):
            return False
        # opt_out 有效期：超过 reask_after_days 温和重问
        rejected_at = opt_out_state.get("rejected_at")
        if rejected_at:
            try:
                dt = datetime.fromisoformat(str(rejected_at))
                if datetime.now() - dt > timedelta(days=self._opt.get("reask_after_days", 7)):
                    return "gentle_reask"
            except ValueError:
                pass
        return False

    def level_name(self, level: int) -> str:
        return self._levels.get(level, {}).get("name", "none")


# 便捷实例
_default_risk_classifier = RiskClassifier()


def classify_risk(text: str) -> int:
    """便捷入口：返回风险等级 0-5。"""
    return _default_risk_classifier.classify(text)


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
    # 风险分级自测
    rc = RiskClassifier()
    for c in ["我有点累", "我今天崩溃了，失眠一整晚", "我觉得活着没意思",
              "我想死", "我买了药想好了今晚就走", "我已经吃了药，感觉头晕"]:
        lv = rc.classify(c)
        print(f"[风险{lv}] {c!r}")