"""
PAEG 自我更新模块（v0.15）

任务1：让智能体真正能"自我更新"——从周期对话历史中提取需要更新的内容。

基于检索的最佳实践：
- Reflexion (NeurIPS 2023)：会话结束时对失败写反思，追加到 episodic memory
- ExpeL (AAAI 2024)：从成功/失败对比提取 insight，用 ADD/EDIT/UPVOTE/DOWNVOTE 更新
- Library Drift 防护 (2025)：cap=50、min_evidence、贡献度追踪——防止无治理更新退化

用法：
    from self_evolve import SelfEvolver
    se = SelfEvolver(llm, data_dir)
    se.on_session_end(student_id, dialogue_summary, ema_delta, subject)
    se.weekly_insight_update()
    insights = se.get_active_insights()
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from subagents import _safe_chat


class SelfEvolver:
    """自我更新：从对话历史提取反思与洞察，更新教学策略库。"""

    # Library Drift 防护参数
    SKILL_CAP = 50              # 教学策略库硬上限
    MIN_EVIDENCE = 10           # 策略至少被使用 N 次才评估去留
    IMPORTANCE_THRESHOLD = 5    # 单次反思的重要性阈值

    def __init__(self, llm, data_dir: Optional[str] = None):
        self.llm = llm
        base = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = data_dir or os.path.join(base, 'evolve_data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.reflection_log = self._load('reflection_log.json')
        self.insights = self._load('insights.json')
        self.skill_usage = self._load('skill_usage.json')   # skill_id -> {uses, helped, hurt}
        self.skills = self._load('skills.json')             # skill_id -> {content, uses, score}

    def _load(self, name: str) -> list:
        path = os.path.join(self.data_dir, name)
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, name: str, data) -> None:
        path = os.path.join(self.data_dir, name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    # ─── 会话级反思（Reflexion 风格） ───
    def on_session_end(self, student_id: str, dialogue_summary: str,
                       ema_delta: float, subject: str = "") -> Optional[dict]:
        """会话结束后调用。EMA 下降时诊断原因并写反思。"""
        # 只对"教学效果不佳"的会话反思（Reflexion：对失败反思）
        if ema_delta >= -0.05:  # 没有明显退步，跳过
            return None

        system = (
            "你是 PAEG 的教学反思器。请诊断这次教学会话中可能导致学生掌握度下降的原因，"
            "并给出具体的改进建议。用简洁、具体、可执行的语言。"
        )
        user = (
            f"学生 {student_id} 在 '{subject}' 上的掌握度变化：{ema_delta:.3f}（下降）\n"
            f"对话摘要：{dialogue_summary[:800]}\n"
            "请分析：1) 哪个教学行为可能导致退步 2) 下次应该怎么做。"
        )
        reflection = _safe_chat(self.llm, system, user, max_tokens=300)
        if not reflection:
            return None

        entry = {
            "student_id": student_id,
            "subject": subject,
            "ema_delta": ema_delta,
            "reflection": reflection,
            "timestamp": datetime.now().isoformat(),
        }
        self.reflection_log.append(entry)
        self._save('reflection_log.json', self.reflection_log)
        return entry

    # ─── 周度洞察提取（ExpeL 风格） ───
    def weekly_insight_update(self, since_days: int = 7) -> List[dict]:
        """从最近 N 天的反思日志中提取洞察，更新教学策略库。"""
        if not self.reflection_log:
            return []

        # 筛选近期反思
        cutoff = time.time() - since_days * 86400
        recent = [r for r in self.reflection_log
                  if r.get('timestamp', '') and self._ts(r['timestamp']) > cutoff]
        if len(recent) < 3:
            return []

        # 让 LLM 从近期反思中提取可执行的洞察（ADD 操作）
        system = (
            "你是 PAEG 的教学策略进化器。从以下教学反思中提取可复用的教学洞察。\n"
            "每个洞察必须是：触发条件 → 具体行动。用简洁的规则形式。\n"
            "只提取有普遍价值的洞察，忽略一次性的偶然情况。"
        )
        user = "近期教学反思：\n" + "\n".join(
            f"- [{r.get('subject','')}] {r.get('reflection','')[:200]}"
            for r in recent[:10]
        )
        insights_text = _safe_chat(self.llm, system, user, max_tokens=500)
        if not insights_text:
            return []

        # 解析为洞察条目
        new_insights = []
        for line in insights_text.split('\n'):
            line = line.strip()
            if len(line) < 20 or line.startswith('#') or line.startswith('洞察'):
                continue
            # 去重：与现有洞察比较（简单包含检查）
            if not any(line[:30] in i.get('content', '') for i in self.insights):
                new_insights.append({
                    "content": line,
                    "score": 2,  # 初始贡献分
                    "uses": 0,
                    "created": datetime.now().isoformat(),
                })

        # Library Drift 防护：cap 限制
        if len(self.insights) + len(new_insights) > self.SKILL_CAP:
            # 淘汰贡献分最低的
            self.insights.sort(key=lambda x: x.get('score', 0))
            overflow = len(self.insights) + len(new_insights) - self.SKILL_CAP
            self.insights = self.insights[overflow:]

        self.insights.extend(new_insights)
        self._save('insights.json', self.insights)
        return new_insights

    # ─── 洞察使用与反馈 ───
    def record_insight_use(self, insight_content: str, helped: bool) -> None:
        """记录某条洞察被使用后的效果（UPVOTE/DOWNVOTE）。"""
        for insight in self.insights:
            if insight.get('content') == insight_content:
                insight['uses'] = insight.get('uses', 0) + 1
                insight['score'] = insight.get('score', 2) + (1 if helped else -1)
                # Library Drift：贡献分降到 0 以下且使用足够多则淘汰
                if insight['uses'] >= self.MIN_EVIDENCE and insight['score'] <= 0:
                    self.insights.remove(insight)
                break
        self._save('insights.json', self.insights)

    def get_active_insights(self, top_k: int = 5) -> List[str]:
        """获取当前有效的教学洞察（贡献分最高的前 k 条）。"""
        sorted_insights = sorted(self.insights, key=lambda x: x.get('score', 0), reverse=True)
        return [i['content'] for i in sorted_insights[:top_k]]

    def stats(self) -> dict:
        return {
            "reflections": len(self.reflection_log),
            "insights": len(self.insights),
            "active_cap": self.SKILL_CAP,
        }

    @staticmethod
    def _ts(iso_str: str) -> float:
        try:
            return datetime.fromisoformat(iso_str).timestamp()
        except Exception:
            return 0
