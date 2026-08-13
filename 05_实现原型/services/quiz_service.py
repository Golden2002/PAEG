# -*- coding: utf-8 -*-
"""交互式教学选择题服务（v0.67 ⭐ Oracle 设计 MVP）

用户需求：教学环节出选择题推动教学过程——LLM 出题（题干+4选项）→
前端点选 → 判断对错 → 掌握度更新 → 推进教学。

MVP：按钮触发（测试我一下）+ 交互卡片 + 掌握度反馈（EMA）。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Dict, Optional, List

# 内存题库（TTL 10 分钟，防泄漏 + 一题一答）
QUIZ_STORE: Dict[str, dict] = {}
QUIZ_TTL = 600  # 秒

# 掌握度 EMA 系数
QUIZ_MASTERY_ALPHA = 0.2

# v0.67 ⭐ 内置题库（LLM 失败时的确定性真实题——非自评题）
_BUILTIN_QUIZ = [
    {
        "concepts": ("极限", "lim"),
        "stem": "函数 f(x) 当 x 趋近 a 时的极限为 L 的含义是：",
        "options": ["f(a) = L", "当 x 无限接近 a 时，f(x) 无限接近 L",
                    "f(x) 在 a 处必须有定义", "x 必须等于 a 时才有极限"],
        "correct_idx": 1,
        "explanation": "极限描述的是 x 趋近 a 时 f(x) 的趋近行为，不要求 f(a) 有定义。",
    },
    {
        "concepts": ("导数", "微积分"),
        "stem": "函数 f 在 x=a 处的导数 f'(a) 的几何意义是：",
        "options": ["函数在 a 点的函数值", "函数图像在 a 点的切线斜率",
                    "函数在 a 点的凹凸性", "函数在 [a, b] 区间的平均变化率"],
        "correct_idx": 1,
        "explanation": "导数 f'(a) 就是曲线 y=f(x) 在点 (a, f(a)) 处切线的斜率。",
    },
    {
        "concepts": ("二次函数", "抛物线"),
        "stem": "二次函数 y = x² - 4x + 3 的顶点坐标是：",
        "options": ["(2, -1)", "(-2, 3)", "(4, 3)", "(0, 3)"],
        "correct_idx": 0,
        "explanation": "配方得 y = (x-2)² - 1，顶点为 (2, -1)。",
    },
    {
        "concepts": ("矩阵", "线性代数"),
        "stem": "矩阵乘法 A×B 能进行的前提是：",
        "options": ["A 和 B 都是方阵", "A 的列数 = B 的行数",
                    "A 的行数 = B 的列数", "A 和 B 同型"],
        "correct_idx": 1,
        "explanation": "A(m×n) 与 B(n×p) 可乘，要求 A 的列数 = B 的行数。",
    },
    {
        "concepts": ("概率", "统计"),
        "stem": "掷两枚均匀骰子，点数之和为 7 的概率是：",
        "options": ["1/6", "1/12", "1/36", "5/36"],
        "correct_idx": 0,
        "explanation": "和为 7 的组合有 6 种（1+6,2+5,3+4,4+3,5+2,6+1），总 36 种，概率 6/36=1/6。",
    },
    {
        "concepts": ("向量", "几何"),
        "stem": "两个非零向量 a、b 垂直的充要条件是：",
        "options": ["a·b = 0", "a·b > 0", "a 与 b 共线", "|a| = |b|"],
        "correct_idx": 0,
        "explanation": "垂直 ⇔ 数量积 a·b = 0（两非零向量）。",
    },
]


def _builtin_quiz_for(concept: str) -> Optional[dict]:
    """按概念关键词匹配内置题（真实知识点题）。"""
    if not concept:
        return None
    c = concept.lower()
    for q in _BUILTIN_QUIZ:
        if any(k in c for k in q["concepts"]):
            return q
    return None


def _store(quiz_id: str, data: dict):
    data['_expires'] = time.time() + QUIZ_TTL
    data['_answered'] = False
    QUIZ_STORE[quiz_id] = data


def _get_valid(quiz_id: str) -> Optional[dict]:
    q = QUIZ_STORE.get(quiz_id)
    if not q:
        return None
    if time.time() > q.get('_expires', 0):
        QUIZ_STORE.pop(quiz_id, None)
        return None
    return q


def generate_choice(learner, subject: str, concept: str,
                    difficulty: int = 1, previous_concepts: Optional[List[str]] = None) -> dict:
    """LLM 生成一道 4 选项选择题。

    返回 {quiz_id, stem, options[4], concept, difficulty, retry_of}
    失败 → 确定性兜底题（UI 不死锁）。
    """
    grade = getattr(learner, 'grade_level', 'high_school')
    grade_cn = {'middle_school': '初中', 'high_school': '高中',
                'undergraduate': '本科', 'graduate_exam': '考研'}.get(grade, grade)
    qid = 'qz_%s_%s' % (time.strftime('%Y%m%d%H%M'), uuid.uuid4().hex[:4])

    prompt = (
        f"你是{grade_cn}{subject}老师。为概念「{concept}」出一道单项选择题。\n"
        "要求：\n"
        "1. 题干清晰、考查核心理解（非记忆）\n"
        "2. 4 个选项，只有一个正确，干扰项有迷惑性\n"
        "3. 难度：" + {0: '基础', 1: '中等', 2: '进阶'}.get(difficulty, '中等') + "\n"
        "4. 只输出 JSON：{\"stem\": \"题干\", \"options\": [\"A\",\"B\",\"C\",\"D\"], "
        "\"correct_idx\": 0-3, \"explanation\": \"解析（讲清为什么）\"}\n"
        "5. 不要输出 JSON 以外任何文字"
    )
    try:
        from subagents import _safe_chat
        from infra.runtime import get_llm
        llm = get_llm()
        parsed = None
        # v0.67 ⭐ 重试 2 次（DeepSeek 偶发空响应/JSON 解析失败）
        for _attempt in range(3):
            r = _safe_chat(llm, prompt, f"概念：{concept}", max_tokens=400)
            if r:
                clean = r.strip()
                if clean.startswith('```'):
                    clean = clean.split('```')[1].lstrip('json').strip()
                try:
                    parsed = json.loads(clean)
                    break
                except Exception:
                    m = re.search(r'\{[^{}]*"stem"[^{}]*\}', clean, re.S)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                            break
                        except Exception:
                            parsed = None
            import time as _t
            _t.sleep(1.0)
        if parsed and isinstance(parsed.get('options'), list) and len(parsed['options']) == 4:
            opts = [str(o)[:120] for o in parsed['options']]
            data = {
                'quiz_id': qid,
                'stem': str(parsed.get('stem', ''))[:300],
                'options': opts,
                'correct_idx': int(parsed.get('correct_idx', 0)) % 4,
                'explanation': str(parsed.get('explanation', ''))[:300],
                'concept': concept,
                'difficulty': difficulty,
                'retry_of': None,
            }
            if data['stem'] and all(data['options']):
                _store(qid, data)
                return {k: v for k, v in data.items() if not k.startswith('_')}
    except Exception as _e:
        print(f"[PAEG][quiz_service] 出题失败: {_e}")

    # v0.67 ⭐ 兜底优先内置题库（真实知识点题，非自评题）
    _bq = _builtin_quiz_for(concept)
    if _bq:
        qid2 = 'qz_%s_%s' % (time.strftime('%Y%m%d%H%M'), uuid.uuid4().hex[:4])
        data = {
            'quiz_id': qid2,
            'stem': _bq['stem'],
            'options': list(_bq['options']),
            'correct_idx': _bq['correct_idx'],
            'explanation': _bq['explanation'],
            'concept': concept,
            'difficulty': difficulty,
            'retry_of': None,
        }
        _store(qid2, data)
        return {k: v for k, v in data.items() if not k.startswith('_')}

    # 自评兜底（无内置题匹配时，描述更丰富引导自定义回答）
    fb = {
        'quiz_id': qid,
        'stem': f'关于「{concept}」，请选择最符合你当前掌握程度的选项。'
                f'（本题为自评题：如果选项都不合适，可以直接在下方输入框描述你的理解，'
                f'例如"我大概知道 {concept} 的定义，但不会算题目"。）',
        'options': ['A. 我已掌握基本概念，可以继续', 'B. 大致了解，需要例题巩固',
                    'C. 听过但很模糊，需要重新讲解', 'D. 完全陌生，从零开始'],
        'correct_idx': 0,
        'explanation': '这是自评题——你的选择或输入会直接告诉我该从哪一步继续教学，'
                       f'我会根据你的反馈调整对「{concept}」的讲解节奏。',
        'concept': concept,
        'difficulty': difficulty,
        'retry_of': None,
    }
    _store(qid, fb)
    return {k: v for k, v in fb.items() if not k.startswith('_')}


def grade_answer(learner, quiz_id: str, selected_idx: int) -> dict:
    """判题 + 掌握度更新。

    返回 {correct, correct_idx, explanation, mastery_delta, new_mastery,
          suggested_next, feedback_zh}
    """
    q = _get_valid(quiz_id)
    if not q:
        return {'correct': False, 'correct_idx': -1, 'error': 'quiz_expired'}
    if q.get('_answered'):
        return {'correct': False, 'correct_idx': q.get('correct_idx', -1),
                'error': 'already_answered'}
    q['_answered'] = True

    correct = (int(selected_idx) == int(q.get('correct_idx', 0)))
    delta = 0.08 if correct else -0.15
    concept = q.get('concept', '')

    # 掌握度更新（EMA）
    new_mastery = None
    try:
        sm = getattr(learner, 'subjects_mastery', None)
        if isinstance(sm, dict):
            entry = sm.get(concept) or {}
            if isinstance(entry, dict):
                old = entry.get('mastery', 0.5)
            else:
                old = 0.5
            new = old + QUIZ_MASTERY_ALPHA * (delta)
            new = max(0.0, min(1.0, new))
            if isinstance(sm, dict):
                sm[concept] = {'mastery': round(new, 3),
                               'count': (entry.get('count', 0) if isinstance(entry, dict) else 0) + 1}
            new_mastery = round(new, 3)
    except Exception:
        pass

    # 教学推进建议 + 过渡语（v0.67 ⭐ 前后衔接：判题后自然过渡到下一步）
    if correct:
        suggested_next = 'concept'
        feedback_zh = (
            f"太棒了，你的回答是正确的！{q.get('explanation', '')}"
            f"你看，关于「{concept}」你已经理解了。我们继续往下讲。"
        )
    else:
        suggested_next = 'retry'
        feedback_zh = (
            f"这道题很可惜，你选错了。{q.get('explanation', '')}"
            f"没关系，这正好说明「{concept}」还有需要巩固的地方。"
            f"我再讲一遍，然后你再试试，好吗？"
        )

    # v0.67 ⭐ 衔接机制：判题结果写回 chat_hist → 下一次教学能引用（对话连贯）
    try:
        from infra.sessions import SESSIONS
        _uid = str(getattr(learner, "id", "") or "")
        _hist = SESSIONS.setdefault(f"chat_hist_{_uid}", [])
        _hist.append({
            "role": "assistant",
            "content": f"[小测·{concept}] {feedback_zh}",
            "quiz": {"quiz_id": quiz_id, "correct": correct,
                     "concept": concept, "selected_idx": selected_idx},
        })
        if len(_hist) > 60:
            SESSIONS[f"chat_hist_{_uid}"] = _hist[-60:]
    except Exception:
        pass

    return {
        'correct': correct,
        'correct_idx': q.get('correct_idx', -1),
        'explanation': q.get('explanation', ''),
        'mastery_delta': delta,
        'new_mastery': new_mastery,
        'suggested_next': suggested_next,
        'feedback_zh': feedback_zh,
        'concept': concept,
    }
