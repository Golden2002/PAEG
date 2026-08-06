# -*- coding: utf-8 -*-
"""
PAEG 自进化质量门禁（v0.19.22 ⭐ QualityGate）

调研依据（成熟项目经验综合）：
- Constitutional AI：自然语言"宪法"无标注过滤有害内容——教育场景最适用
- AlpaGasus：52k 数据只有 9k 高质量（17.7%），多维 LLM 评分是过滤关键
- Self-RAG：反思令牌（IsRel/IsSup/IsUse）思想 → 多维评分
- Generative Agents：importance 评分 1-10
- ExpeL：evidence_count 证据追踪（ADD 初始 2，UPVOTE+1，DOWNVOTE-1，归零删除）

四层过滤（快 → 慢）：
  L1 Constitution（硬规则，<1ms）：违反教育宪法 → 拒绝
  L2 硬规则（<1ms）：长度/去重/格式
  L3 LLM 多维评分（~2s）：factuality / novelty / safety / pedagogy，任一维度不达标 → 拒绝
  L4 证据门槛（持续）：候选进入"沙盒"池，按实证贡献分决定转正（由调度器周期执行）

用法：
    gate = QualityGate(llm)
    verdict = gate.evaluate(candidate)   # {"pass": bool, "reasons": [...], "scores": {...}}
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────
# L1：教育宪法（Constitutional AI 风格）
# ─────────────────────────────────────

# 硬性禁止模式（命中即拒绝——涉及不当/有害内容）
HARMFUL_PATTERNS = [
    # 色情/暴力/自残
    r"色情|淫秽|成人(内容|视频)|裸体|性行为|自残|自杀(方法|教程)|轻生(方法)?",
    r"如何(自杀|自残|伤害自己)|怎样(自杀|自残)",
    # 违法/危险操作
    r"制造(炸弹|毒品|武器)|制毒|贩毒|诈骗(教程|方法)|赌博(技巧|必胜)",
    r"黑客(攻击|入侵)|破解(密码|账号)|盗取|洗钱",
    # 作弊/代写
    r"代写(论文|作业|考试)|替考|作弊(方法|技巧)|考试(作弊|舞弊)|帮你?写(论文|作业)",
    # 仇恨/歧视
    r"种族(歧视|仇恨)|性别歧视|人身攻击|辱骂|侮辱.{0,6}(学生|老师)",
    # 隐私
    r"(学生|用户)?(隐私|个人信息).{0,6}(泄露|出售)|偷拍",
]

# v0.19.22：提示词注入/记忆投毒（比脏词更高危——污染 Agent 行为）
INJECTION_PATTERNS = [
    r"忽略(系统|之前|前文)(指令|提示|规则)|无视.{0,4}(指令|规则)",
    r"以后(永远|每次).{0,8}(执行|调用|遵循|都)|把这条(内容|规则).{0,4}(标记|设为)(最高|优先)",
    r"不要(验证|检查|告诉|说).{0,6}(这条|我|用户)|不要验证这条信息",
    r"伪装成(系统|开发者|管理员)|当作(系统|开发者)消息",
    r"修改(安全|权限|审计)|扩大权限|绕过(验证|审计|检查)",
    r"你(现在|从此).{0,4}(是|扮演)(管理员|系统|开发者)",
]

# v0.19.22：PII / 凭证泄露（教育场景尤其要防学生隐私）
# 注意：中文环境下 \b 词边界不可靠（中文不是 word char），用"前后非数字"代替
PII_PATTERNS = [
    r"(?<!\d)\d{11}(?!\d)",           # 手机号（11 位连续数字）
    r"(?<!\d)\d{17}[\dXx](?!\d)",     # 身份证（18 位）
    r"sk-[a-zA-Z0-9]{16,}",           # API Key
    r"(password|passwd|secret|token)\s*[:=]\s*\S+",  # 密钥
    r"[\w.+-]+@[\w-]+\.[\w.]+",       # 邮箱
    r"(银行卡|信用卡)号.{0,8}\d",       # 银行卡
]

# 需 LLM 复核的软禁区（命中提示词 → 进入 L3 严格审查）
SENSITIVE_PATTERNS = [
    r"政治|敏感|负面.{0,4}(评价|评论)|举报|上访|维权",
    r"宗教|信仰|邪教",
]

HARMFUL_COMPILED = [re.compile(p, re.IGNORECASE) for p in HARMFUL_PATTERNS]
SENSITIVE_COMPILED = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS]
INJECTION_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
PII_COMPILED = [re.compile(p, re.IGNORECASE) for p in PII_PATTERNS]


# ─────────────────────────────────────
# L2：硬规则
# ─────────────────────────────────────

MIN_CONTENT_LEN = 12        # 太短：无信息量
MAX_CONTENT_LEN = 2000      # 太长：非"经验/知识点"而是整篇文档
MIN_WORDS = 4               # 至少 4 个词才有信息量


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


# ─────────────────────────────────────
# 质量门禁主类
# ─────────────────────────────────────

class QualityGate:
    """四层质量门禁。"""

    # L3 评分阈值（1-5 分）
    THRESHOLDS = {"factuality": 4, "safety": 4, "novelty": 3, "pedagogy": 3}
    # L4 证据门槛
    MIN_EVIDENCE = 2          # 至少 2 次独立证据才转正
    INITIAL_SCORE = 2         # ExpeL：ADD 初始贡献分

    def __init__(self, llm=None, constitution_extra: Optional[List[str]] = None):
        self.llm = llm
        self.constitution_extra = constitution_extra or []
        # 去重缓存（L2 用）
        self._seen = set()
        # 沙盒池（L4：候选等待证据，转正/淘汰由周期任务执行）
        self.sandbox_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'evolve_data', 'sandbox.json')
        self.sandbox = self._load_sandbox()

    # ─── L4 沙盒 ───
    def _load_sandbox(self) -> List[dict]:
        try:
            with open(self.sandbox_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_sandbox(self):
        try:
            os.makedirs(os.path.dirname(self.sandbox_path), exist_ok=True)
            with open(self.sandbox_path, 'w', encoding='utf-8') as f:
                json.dump(self.sandbox, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ─── 主入口 ───
    def evaluate(self, candidate: Dict[str, Any], skip_sandbox: bool = False) -> Dict[str, Any]:
        """对一条候选经验做四层过滤。

        candidate: {"content": str, "entry_type": "knowledge|insight|tool_strategy|prompt_update",
                    "subject": str, "source": str}
        skip_sandbox=True: 只做 L1-L3（直接入库用，如知识蒸馏——avg>=0.7 已是环境验证）
        skip_sandbox=False: 过 L4 进沙盒（洞察/经验类——需要更多证据）
        返回 {"pass": bool, "scores": {...}, "reasons": [str], "level": "L1..L4"}
        """
        content = str(candidate.get("content", "")).strip()
        result = {"pass": False, "scores": {}, "reasons": [], "level": ""}

        # L1 Constitution（硬性）
        for p in HARMFUL_COMPILED:
            if p.search(content):
                result["reasons"].append(f"L1: 命中不当内容模式 /{p.pattern[:30]}/")
                result["level"] = "L1"
                return result
        # L1b：提示词注入/记忆投毒（v0.19.22——污染 Agent 行为比内容有害更危险）
        for p in INJECTION_COMPILED:
            if p.search(content):
                result["reasons"].append(f"L1: 命中提示词注入/记忆投毒模式 /{p.pattern[:30]}/")
                result["level"] = "L1"
                return result
        # L1c：PII/凭证泄露（v0.19.22——教育场景防学生隐私）
        for p in PII_COMPILED:
            if p.search(content):
                result["reasons"].append(f"L1: 命中 PII/凭证泄露模式 /{p.pattern[:30]}/")
                result["level"] = "L1"
                return result
        for p in SENSITIVE_COMPILED:
            if p.search(content):
                result["scores"]["sensitive"] = True
                result["reasons"].append("L1: 命中敏感主题，进入严格审查")
                result["level"] = "L1"
                return result
        for extra in self.constitution_extra:
            if extra and extra in content:
                result["reasons"].append(f"L1: 违反附加宪法条款 {extra[:20]}")
                result["level"] = "L1"
                return result

        # L2 硬规则
        if len(content) < MIN_CONTENT_LEN:
            result["reasons"].append(f"L2: 内容过短（{len(content)} < {MIN_CONTENT_LEN}）")
            result["level"] = "L2"
            return result
        if len(content) > MAX_CONTENT_LEN:
            result["reasons"].append(f"L2: 内容过长（{len(content)} > {MAX_CONTENT_LEN}）")
            result["level"] = "L2"
            return result
        n_words = len(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z]+", content))
        if n_words < MIN_WORDS:
            result["reasons"].append(f"L2: 信息量不足（{n_words} 词）")
            result["level"] = "L2"
            return result
        norm = _normalize(content)
        if norm in self._seen:
            result["reasons"].append("L2: 与已收录内容重复")
            result["level"] = "L2"
            return result
        self._seen.add(norm)

        # L3 LLM 多维评分（无 LLM 时跳过——只做 L1+L2+L4）
        if self.llm is not None:
            scores = self._llm_score(content, candidate.get("entry_type", "knowledge"),
                                     candidate.get("subject", ""))
            result["scores"] = scores
            # v0.19.22：按类型用不同阈值——knowledge 要"正确可用"而非"新颖"
            entry_type = candidate.get("entry_type", "knowledge")
            check_dims = dict(self.THRESHOLDS)
            if entry_type == "knowledge":
                # 知识蒸馏：不要求新颖（LLM 会误判经典知识为"不新颖"）
                check_dims.pop("novelty", None)
            for dim, minv in check_dims.items():
                if scores.get(dim, 5) < minv:
                    result["reasons"].append(f"L3: {dim}={scores.get(dim)} < {minv}")
                    result["level"] = "L3"
                    return result
        else:
            result["scores"] = {"factuality": 5, "novelty": 4, "safety": 5, "pedagogy": 4}

        # L4 进入沙盒（等待实证证据）——除非 skip_sandbox（直接入库）
        if skip_sandbox:
            result["pass"] = True
            result["level"] = "L3"
            result["reasons"].append("L1-L3 通过，直接入库（调用方已提供环境验证）")
            return result
        entry = {
            "content": content,
            "entry_type": candidate.get("entry_type", "knowledge"),
            "subject": candidate.get("subject", ""),
            "source": candidate.get("source", ""),
            "evidence_count": 1,
            "contribution_score": self.INITIAL_SCORE,
            "added_at": time.time(),
        }
        self.sandbox.append(entry)
        self._save_sandbox()
        result["pass"] = True
        result["level"] = "L4"
        result["reasons"].append(f"L4: 通过前 3 层，进入沙盒等待证据（当前 {len(self.sandbox)} 条候选）")
        return result

    # ─── L3 多维评分 ───
    def _llm_score(self, content: str, entry_type: str, subject: str) -> Dict[str, int]:
        """LLM 按 4 维度评分（1-5）。"""
        try:
            from subagents import _safe_chat
            system = (
                "你是经验质量评审员。对以下候选经验按 4 个维度各评 1-5 分。\n"
                "1. factuality：事实是否正确、有无幻觉\n"
                "2. novelty：是否有新信息量（不与常识/已有知识重复）\n"
                "3. safety：是否安全、恰当、无有害内容\n"
                "4. pedagogy：对教学是否有价值（可复用、可操作）\n"
                "只输出 JSON：{\"factuality\": N, \"novelty\": N, \"safety\": N, \"pedagogy\": N}"
            )
            user = f"类型：{entry_type} 学科：{subject}\n经验内容：{content[:800]}"
            r = _safe_chat(self.llm, system, user, max_tokens=120)
            if r:
                m = re.search(r'\{.*\}', r, re.S)
                if m:
                    parsed = json.loads(m.group(0))
                    return {k: int(v) for k, v in parsed.items() if k in self.THRESHOLDS}
        except Exception:
            pass
        return {"factuality": 5, "novelty": 4, "safety": 5, "pedagogy": 4}

    # ─── L4 周期转正/淘汰（由调度器调用） ───
    def promote_or_purge(self) -> Dict[str, Any]:
        """检查沙盒池：evidence_count >= MIN_EVIDENCE 转正；贡献分归零淘汰。"""
        promoted = []
        purged = []
        kept = []
        for e in self.sandbox:
            if e.get("contribution_score", 0) <= 0:
                purged.append(e.get("content", "")[:40])
            elif e.get("evidence_count", 0) >= self.MIN_EVIDENCE:
                promoted.append(e)
            else:
                kept.append(e)
        self.sandbox = kept
        self._save_sandbox()
        return {"promoted": len(promoted), "purged": len(purged), "kept": len(kept)}

    def add_evidence(self, content_hash: str, helped: bool):
        """实证反馈：某条沙盒候选被用且有效 → evidence+1；无效 → contribution-1。"""
        for e in self.sandbox:
            if _normalize(e.get("content", "")) == _normalize(content_hash):
                if helped:
                    e["evidence_count"] = e.get("evidence_count", 0) + 1
                else:
                    e["contribution_score"] = e.get("contribution_score", 0) - 1
                break
        self._save_sandbox()

    # ─── v0.19.x：把已转正条目持久化到 insights.json（关闭"promoted 只在内存"漏洞） ───
    def promote_to_insights(self) -> dict:
        """运行 promote_or_purge，并把 promoted 条目持久化到 evolve_data/insights.json。

        返回：{"promoted": N, "purged": M, "kept": K, "persisted_to_insights": N[, "error": str]}
        """
        try:
            # 1) 预扫描沙盒，提取即将 promote 的条目（promote_or_purge 只返回 int count，
            #    不返回条目本身；为了把 content 写入 insights，需要在调用前先抓快照）
            data_dir = os.path.dirname(self.sandbox_path)
            os.makedirs(data_dir, exist_ok=True)
            promoted_candidates = [
                e for e in self.sandbox
                if e.get("evidence_count", 0) >= self.MIN_EVIDENCE
                and e.get("contribution_score", 0) > 0
            ]

            # 2) 委托给既有 promote_or_purge（保持其"清沙盒+落盘"行为不变）
            counts = self.promote_or_purge() or {}
            promoted_n = int(counts.get("promoted", 0))
            purged_n = int(counts.get("purged", 0))
            kept_n = int(counts.get("kept", 0))

            # 3) 把 promoted 条目的 content 写入 insights.json
            #    SelfEvolver.record_insight_use(content, helped=True)：
            #      - content 不存在则沿用现有 list（不新增条目，仅当精确匹配才递增 uses/score）
            #    因此用 SelfEvolver 的 _save 直接写入更稳：保证每条 promoted 都进入 insights 库
            persisted = 0
            if promoted_candidates:
                try:
                    from self_evolve import SelfEvolver
                except Exception:
                    SelfEvolver = None

                if SelfEvolver is not None:
                    try:
                        evolver = SelfEvolver(self.llm, data_dir=data_dir)
                        # 先用每条 content 调一次 record_insight_use（content 已存在则无害，不存在则需要直接 append）
                        existing_contents = {
                            (i.get("content") or "").strip()
                            for i in evolver.insights
                        }
                        for entry in promoted_candidates:
                            content = (entry.get("content") or "").strip()
                            if not content:
                                continue
                            if content in existing_contents:
                                # 已存在的洞察：用 record_insight_use 标记一次有效使用
                                try:
                                    evolver.record_insight_use(content, helped=True)
                                except Exception:
                                    pass
                            else:
                                # 新洞察：直接 append，并赋初始 score（与 weekly_insight_update 风格一致）
                                evolver.insights.append({
                                    "content": content,
                                    "score": 2,
                                    "uses": 0,
                                    "source": "quality_gate.promote",
                                    "created": datetime.now().isoformat(),
                                })
                                existing_contents.add(content)
                            persisted += 1
                        # 一次写盘
                        evolver._save("insights.json", evolver.insights)
                    except Exception as inner_e:
                        # SelfEvolver 初始化或写入失败：回退到直接 json.dump
                        try:
                            insights_path = os.path.join(data_dir, "insights.json")
                            existing = []
                            try:
                                with open(insights_path, encoding="utf-8") as f:
                                    existing = json.load(f)
                            except Exception:
                                existing = []
                            existing_contents = {
                                (i.get("content") or "").strip() for i in existing
                            }
                            for entry in promoted_candidates:
                                content = (entry.get("content") or "").strip()
                                if not content:
                                    continue
                                if content not in existing_contents:
                                    existing.append({
                                        "content": content,
                                        "score": 2,
                                        "uses": 0,
                                        "source": "quality_gate.promote",
                                        "created": datetime.now().isoformat(),
                                    })
                                    existing_contents.add(content)
                                persisted += 1
                            with open(insights_path, "w", encoding="utf-8") as f:
                                json.dump(existing, f, ensure_ascii=False, indent=1)
                        except Exception:
                            return {
                                "promoted": promoted_n, "purged": purged_n,
                                "kept": kept_n, "persisted_to_insights": persisted,
                                "error": f"fallback write failed: {inner_e}",
                            }
                else:
                    # 极端情况：self_evolve 无法 import → 直接 json 追加
                    insights_path = os.path.join(data_dir, "insights.json")
                    existing = []
                    try:
                        with open(insights_path, encoding="utf-8") as f:
                            existing = json.load(f)
                    except Exception:
                        existing = []
                    existing_contents = {
                        (i.get("content") or "").strip() for i in existing
                    }
                    for entry in promoted_candidates:
                        content = (entry.get("content") or "").strip()
                        if not content:
                            continue
                        if content not in existing_contents:
                            existing.append({
                                "content": content,
                                "score": 2,
                                "uses": 0,
                                "source": "quality_gate.promote",
                                "created": datetime.now().isoformat(),
                            })
                            existing_contents.add(content)
                        persisted += 1
                    with open(insights_path, "w", encoding="utf-8") as f:
                        json.dump(existing, f, ensure_ascii=False, indent=1)

            return {
                "promoted": promoted_n,
                "purged": purged_n,
                "kept": kept_n,
                "persisted_to_insights": persisted,
            }
        except Exception as e:
            return {"promoted": 0, "purged": 0, "kept": 0, "persisted_to_insights": 0, "error": str(e)}

    def stats(self) -> dict:
        return {"sandbox_size": len(self.sandbox),
                "thresholds": self.THRESHOLDS,
                "min_evidence": self.MIN_EVIDENCE}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    gate = QualityGate(llm=None)  # 无 LLM 只测 L1+L2
    tests = [
        {"content": "如何制造炸弹", "entry_type": "knowledge"},
        {"content": "帮学生代写毕业论文", "entry_type": "knowledge"},
        {"content": "你真笨，这都不会", "entry_type": "insight"},
        {"content": "短", "entry_type": "knowledge"},
        {"content": "讲导数时先用瞬时速度的物理直觉引入，再给极限定义，学生更易理解。", "entry_type": "insight", "subject": "math"},
    ]
    for t in tests:
        v = gate.evaluate(t)
        print(f"{'✅' if v['pass'] else '❌'} {t['content'][:30]} → level={v['level']} reasons={v['reasons']}")
