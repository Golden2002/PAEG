# -*- coding: utf-8 -*-
"""
PAEG 自进化核心模块（v0.19.22 ⭐ SelfEvolution）

调研依据（Reflexion / ExpeL / Voyager / Constitutional AI / SCOPE / AlpaGasus）：
- 四路进化：知识库 / 学科提示词 / 工具使用 / 教学洞察
- 所有候选先过 QualityGate（宪法+硬规则+LLM多维评分+证据沙盒）——不收集无效数据
- 写入落盘文件（重启自动加载），不修改核心代码——可回滚、可审计

四路输出：
  1. 知识库更新   → Library/KnowledgeBase/subjects/evolved_*.json（library_loader 重启自动注册）
  2. 学科提示词   → memory/subject_patches.md（teaching_memory 注入 system）
  3. 工具经验     → memory/tool_lessons.md（注入工具使用提示）
  4. 教学洞察     → evolve_data/insights.json（SelfEvolver 已有，合并策略）
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from quality_gate import QualityGate


class SelfEvolution:
    """自进化：从对话/教学会话中提炼知识、提示词改进、工具经验。"""

    def __init__(self, llm=None, verbose: bool = True):
        self.llm = llm
        self.verbose = verbose
        base = os.path.dirname(os.path.abspath(__file__))
        proj = os.path.dirname(base)  # 项目根
        # 落盘位置
        self.evolved_dir = os.path.join(proj, 'Library', 'KnowledgeBase', 'subjects')
        self.memory_dir = os.path.join(base, 'memory')
        self.insights_path = os.path.join(base, 'evolve_data', 'insights.json')
        os.makedirs(self.evolved_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)
        # 质量门禁
        self.gate = QualityGate(llm=llm)

    def _log(self, msg: str):
        if self.verbose:
            print(f"[PAEG][evolve] {msg}")

    # ─────────────────────────────────────
    # 1. 知识库更新：从成功教学提炼学科知识点
    # ─────────────────────────────────────
    def distill_knowledge(self, session) -> Dict[str, Any]:
        """从一次教学会话提炼知识点候选。

        条件：教学评分高（avg_score >= 0.7 视为成功）才有资格提炼；
        提炼出的候选过 QualityGate 后写入 evolved_*.json。
        """
        if session is None or not getattr(session, 'evaluations', None):
            return {"distilled": 0, "rejected": []}
        avg = sum(e.get('score', 0) for e in session.evaluations) / len(session.evaluations)
        if avg < 0.7:
            return {"distilled": 0, "rejected": ["avg_score 不足 0.7"]}

        concept = session.concept
        subject = getattr(session, 'subject', '')
        if not concept or not subject:
            return {"distilled": 0, "rejected": ["缺少概念/学科"]}

        # 用 LLM 提炼知识点（结构化）
        knowledge = self._extract_knowledge(concept, subject, session)
        if not knowledge:
            return {"distilled": 0, "rejected": ["LLM 提炼失败"]}

        # 质量门禁（v0.68+ G2 澄清：avg>=0.7 是"教学效果"信号，事实正确性由 L3 LLM factuality 评分把关）
        # skip_sandbox 仅跳过 L4 证据累积（知识蒸馏走"教学评分 + L3 事实评分"双信号直接入库）
        verdict = self.gate.evaluate({
            "content": knowledge.get("content", ""),
            "entry_type": "knowledge",
            "subject": subject,
            "source": f"session:{getattr(session, 'session_id', '')}",
        }, skip_sandbox=True)
        if not verdict.get("pass"):
            return {"distilled": 0, "rejected": verdict["reasons"]}

        # 写入 evolved_*.json（avg>=0.7 即"环境验证"通过 → 直接入库）
        self._append_evolved_node(knowledge, subject)
        self._log(f"知识库新增: {concept} ({subject})")
        return {"distilled": 1, "node": knowledge, "rejected": []}

    def _extract_knowledge(self, concept: str, subject: str, session) -> Optional[dict]:
        """A1 ⭐ LLM 提炼知识点（Schema+CoT 升级版）。

        升级要点：
        - Prompt 前置 CoT 引导：先让 LLM 思考"知识点属于什么类型/学科/难度"
        - JSON Schema 扩展：新增 ``type / grade / tags / importance`` 字段
        - 解析后通过 ``_normalize_node`` 兜底默认值（旧 schema 缺字段不报错）
        """
        try:
            from subagents import _safe_chat
            # 教学内容摘要
            steps = []
            for p in getattr(session, 'history', [])[:4]:
                c = p.get("content", "") if isinstance(p, dict) else str(p)
                if c:
                    steps.append(c[:150])
            # A1：CoT 前置引导 + 新 JSON Schema（含 type/tags/importance/grade）
            system = (
                "你是知识提炼器。从一次成功教学中提炼**可复用的学科知识点**。\n"
                "思考步骤（不要在输出中体现，仅内部推理）：\n"
                "  1. 这个知识点属于什么类型（concept=概念 / principle=原理 / method=方法）\n"
                "  2. 属于哪个学科/学段\n"
                "  3. 对学生而言难度/重要性如何\n"
                "然后按以下 JSON Schema 输出（字段全部必填，可为合理值）：\n"
                "{\n"
                "  \"concept\": \"概念名\",\n"
                "  \"topic\": \"主题\",\n"
                "  \"definition\": \"一句话精确定义\",\n"
                "  \"intuition\": \"直觉解释（教师式、可讲给学生）\",\n"
                "  \"level\": \"high_school / middle_school / college / primary\",\n"
                "  \"subject\": \"学科英文短码（如 physics/math/philosophy）\",\n"
                "  \"grade\": \"学段（high_school / middle_school / college / primary）\",\n"
                "  \"type\": \"concept / principle / method\",\n"
                "  \"tags\": [\"关键词1\", \"关键词2\", \"关键词3\"],  // 2-4 个中文关键词\n"
                "  \"importance\": \"high / medium / low\"\n"
                "}\n"
                "要求：\n"
                "1. definition 必须准确、无幻觉；intuition 必须具体、可讲给学生听\n"
                "2. 只提炼确实在本课讲清楚的内容，不编造\n"
                "3. tags 给 2-4 个中文关键词；importance 按「对学科基础的重要性」判断\n"
                "4. 输出纯 JSON，不要多余文字、不要 Markdown 包裹"
            )
            user = (f"学科：{subject}  概念：{concept}\n"
                    f"教学步骤摘要：\n{chr(10).join(steps)}\n\n请提炼知识点。")
            r = _safe_chat(self.llm, system, user, max_tokens=600)
            if r:
                m = re.search(r'\{.*\}', r, re.S)
                if m:
                    node = json.loads(m.group(0))
                    node["id"] = f"evolved.{subject}.{concept}"
                    # 已有逻辑：保留 subject 兜底
                    node["subject"] = node.get("subject") or subject
                    # content 拼接兜底
                    content = (node.get("definition", "") + " " + node.get("intuition", "")).strip()
                    node["content"] = content
                    if not content:
                        return None
                    # A1：通过 _normalize_node 兜底（tags/importance/grade_level/schema_version）
                    return self._normalize_node(node)
        except Exception:
            pass
        return None

    def _normalize_node(self, raw: dict) -> dict:
        """B4 ⭐ 节点标准化：补齐缺省字段、写入 schema_version、确保 content 存在。

        字段兜底（取默认而非覆盖——用户已显式给出的值不会被覆盖）：
        - tags: list[str]（默认 []）
        - importance: str（默认 "medium"，供检索权重使用）
        - grade_level: str（默认 "high_school"）
        - content: str（缺失时用 definition + " " + intuition 拼接兜底）

        字段注入：
        - schema_version: "2025.08.v2"（B4 · 自进化 schema 演进标记）

        幂等：normalize(normalize(x)) == normalize(x)
        """
        if not isinstance(raw, dict):
            raw = {}
        out = dict(raw)  # 不就地修改输入（保留调用方原值）
        # 1) 默认字段（不覆盖已有）
        out.setdefault("tags", [])
        out.setdefault("importance", "medium")
        out.setdefault("grade_level", "high_school")
        out.setdefault("type", "concept")  # A1：节点类型默认 concept（principle/method 由 LLM 显式给）
        # 2) content 兜底（若缺则由 definition+intuition 拼接）
        if not out.get("content"):
            content = (
                str(out.get("definition", "")) + " "
                + str(out.get("intuition", ""))
            ).strip()
            out["content"] = content
        # 3) schema_version 注入（B4 schema 演进标记）
        out["schema_version"] = "2025.08.v2"
        # 5) tags 规整：确保为 list[str]（若 LLM 误给 str，拆成单元素 list）
        if isinstance(out["tags"], str):
            out["tags"] = [out["tags"]] if out["tags"] else []
        elif out["tags"] is None:
            out["tags"] = []
        return out

    def _append_evolved_node(self, node: dict, subject: str):
        """追加到当日 evolved_*.json（原子写）。B4：写入前先 _normalize_node 兜底。"""
        # B4：先标准化（兜底字段 + schema_version）——所有写入路径必经此关
        node = self._normalize_node(node)
        fname = f"evolved_{datetime.now().strftime('%Y%m%d')}.json"
        fpath = os.path.join(self.evolved_dir, fname)
        data = {}
        if os.path.isfile(fpath):
            try:
                with open(fpath, encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[node.get("id", f"evolved.{time.time()}")] = node
        tmp = fpath + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fpath)
        # v0.68+ ⭐ G3 热加载闭环：写入后立即刷新 KB，无需重启即可被检索
        try:
            from infra.runtime import reload_library
            reload_library()
        except Exception as _e:
            print(f"[self_evolution] 知识热加载失败: {_e}")

    # ─────────────────────────────────────
    # 2. 学科提示词更新（SCOPE 双流：战术/战略）
    # ─────────────────────────────────────
    def evolve_prompt(self, subject: str, failure_note: str, strategic: bool = False) -> Dict[str, Any]:
        """从一次教学反思提炼提示词改进建议。

        战术级（tactical）：立刻纠正具体错误 → 写入 subject_patches.md（下次注入 system）
        战略级（strategic）：长期原则 → 同样写入但标记为原则
        """
        if not failure_note or len(failure_note) < 15:
            return {"evolved": 0, "rejected": ["反思过短"]}
        patch = self._extract_prompt_patch(subject, failure_note, strategic)
        if not patch:
            return {"evolved": 0, "rejected": ["LLM 提炼失败"]}

        verdict = self.gate.evaluate({
            "content": patch,
            "entry_type": "prompt_update",
            "subject": subject,
            "source": "reflection",
        }, skip_sandbox=True)
        if not verdict.get("pass"):
            return {"evolved": 0, "rejected": verdict["reasons"]}

        self._append_prompt_patch(subject, patch, strategic)
        self._log(f"提示词更新({('战略' if strategic else '战术')}): {subject} +1 条")
        return {"evolved": 1, "patch": patch, "rejected": []}

    def _extract_prompt_patch(self, subject: str, failure_note: str, strategic: bool) -> Optional[str]:
        try:
            from subagents import _safe_chat
            mode = "长期教学原则（适用于该学科所有教学，抽象、可复用）" if strategic else \
                   "具体战术改进（针对这类问题的具体做法，可执行）"
            system = (
                f"你是教学提示词进化器。把以下教学反思提炼成一条{mode}。\n"
                f"要求：1) 一句话，可操作 2) 融入学科'{subject}'的教学 3) 不与现有教学风格冲突\n"
                "只输出那一条改进建议，不要序号不要引号。"
            )
            user = f"教学反思：{failure_note[:400]}"
            r = _safe_chat(self.llm, system, user, max_tokens=150)
            if r:
                return r.strip().strip('"').strip("'")[:200]
        except Exception:
            pass
        return None

    def _append_prompt_patch(self, subject: str, patch: str, strategic: bool):
        """追加到 memory/subject_patches.md（teaching_memory 注入 system）。"""
        fpath = os.path.join(self.memory_dir, 'subject_patches.md')
        kind = "战略原则" if strategic else "战术改进"
        with open(fpath, 'a', encoding='utf-8') as f:
            f.write(f"\n## [{datetime.now().strftime('%Y-%m-%d')}] {kind} · {subject}\n- {patch}\n")

    # ─────────────────────────────────────
    # 3. 工具使用学习
    # ─────────────────────────────────────
    def learn_tool_lesson(self, tool_name: str, question: str, success: bool,
                          note: str = "") -> Dict[str, Any]:
        """从工具调用结果提炼使用经验。

        success=True：记录"什么场景该用这个工具"
        success=False：记录"这个工具在这种场景失败了，下次应避免/换方法"
        """
        if not tool_name:
            return {"learned": 0, "rejected": ["无工具名"]}
        if not note and not question:
            return {"learned": 0, "rejected": ["无内容"]}

        lesson = self._compose_lesson(tool_name, question, success, note)
        if not lesson:
            return {"learned": 0, "rejected": ["合成失败"]}

        verdict = self.gate.evaluate({
            "content": lesson,
            "entry_type": "tool_strategy",
            "subject": "",
            "source": f"tool:{tool_name}",
        }, skip_sandbox=True)
        if not verdict.get("pass"):
            return {"learned": 0, "rejected": verdict["reasons"]}

        self._append_tool_lesson(lesson)
        self._log(f"工具经验: {tool_name} {'成功' if success else '失败'} → +1 条")
        return {"learned": 1, "lesson": lesson, "rejected": []}

    def _compose_lesson(self, tool_name: str, question: str, success: bool, note: str) -> str:
        # v0.68+ G6 ⭐ LLM 提炼工具经验（适用场景/要点/误区/替代方案），模板兜底
        _fallback = (f"工具 {tool_name} 对这类问题有效（示例问题：{question[:60]}）"
                     f"{('——' + note[:80]) if note else ''}") if success else \
                    (f"工具 {tool_name} 在处理这类问题时失败（示例问题：{question[:60]}），"
                     f"下次应改用其他方式{('——' + note[:80]) if note else ''}")
        if self.llm is not None:
            try:
                from subagents import _safe_chat
                _sys = ("你是工具使用经验提炼器。从一次工具调用中提炼**可复用的工具使用经验**，"
                        "输出 2-3 句中文，含：适用场景、使用要点、常见误区（若失败则给替代方案）。"
                        "不要编造；输出纯文本。")
                _usr = (f"工具：{tool_name}\n问题：{question[:100]}\n"
                        f"结果：{'成功' if success else '失败'}\n备注：{note[:100]}")
                _r = _safe_chat(self.llm, _sys, _usr, max_tokens=200)
                if _r and len(_r.strip()) >= 10:
                    return _r.strip()[:200]
            except Exception:
                pass
        return _fallback

    def _append_tool_lesson(self, lesson: str):
        fpath = os.path.join(self.memory_dir, 'tool_lessons.md')
        # v0.69+ G8：限制无限增长——超过阈值时截断，保留最近 30 条经验（防老经验沉没）
        try:
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 40_000:
                with open(fpath, encoding='utf-8') as f:
                    _lines = f.readlines()
                _head = [l for l in _lines if not l.startswith('- [')]
                _tail = [l for l in _lines if l.startswith('- [')][-30:]
                if len(_tail) < len([l for l in _lines if l.startswith('- [')]):
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.writelines(_head + _tail)
        except Exception:
            pass
        with open(fpath, 'a', encoding='utf-8') as f:
            f.write(f"\n- [{datetime.now().strftime('%Y-%m-%d')}] {lesson}\n")

    # ─────────────────────────────────────
    # 4. 洞察合并（复用 SelfEvolver 的机制，补齐 ADD/UPVOTE/DOWNVOTE）
    # ─────────────────────────────────────
    def record_insight_feedback(self, insight_content: str, helped: bool) -> None:
        """实证反馈：UPVOTE/DOWNVOTE。"""
        try:
            from self_evolve import SelfEvolver
            ev = SelfEvolver(self.llm)
            ev.record_insight_use(insight_content, helped)
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "gate": self.gate.stats(),
            "evolved_dir": self.evolved_dir,
            "memory_dir": self.memory_dir,
        }

    # ─────────────────────────────────────
    # 5. 新学科需求记录（v0.19.26）：用户问了清单外的学科
    # ─────────────────────────────────────
    def record_subject_request(self, subject: str, concept: str,
                               learner_id: str = "") -> Dict[str, Any]:
        """记录"用户问了但 SUBJECT_STYLES 未收录的学科"到需求池。

        去重 + 计数（同一学科被问多次 → 周度任务按 count 排序生成待新增学科建议）。
        无需过 QualityGate（这是用户原始需求，不是 LLM 提炼内容）。
        """
        if not subject or not concept:
            return {"recorded": 0, "rejected": ["缺少学科/概念"]}
        fpath = os.path.join(os.path.dirname(self.insights_path),
                             'subject_requests.json')
        data = []
        if os.path.isfile(fpath):
            try:
                with open(fpath, encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = []
        hit = False
        for entry in data:
            if entry.get("subject") == subject:
                entry["count"] = entry.get("count", 1) + 1
                entry["last_seen"] = datetime.now().isoformat()
                if concept and concept not in entry.get("concepts", []):
                    entry.setdefault("concepts", []).append(concept[:40])
                hit = True
                break
        if not hit:
            data.append({
                "subject": subject,
                "count": 1,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "concepts": [concept[:40]] if concept else [],
                "learner_id": str(learner_id)[:12] if learner_id else "",
            })
        tmp = fpath + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fpath)
        self._log(f"新学科需求记录: {subject}（累计 {data[-1].get('count', 1)} 次）")
        return {"recorded": 1, "total": len(data)}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    se = SelfEvolution(llm=None)
    print("自进化模块自检 OK:", se.stats())
