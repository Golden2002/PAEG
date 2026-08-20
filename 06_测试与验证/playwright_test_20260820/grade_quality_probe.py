# -*- coding: utf-8 -*-
"""grade_quality_probe.py —— §3.79 Round 8 ⭐ 学段×学科教学质量真实验证

验证：教学模式下，不同学段、学科的对话能否满足相应用户要求——
  - 大学本科：lecture 式知识点讲解（严格定义/定理框架/推导/应用/学科视野）
  - 高中：概念+公式入门 + 题型方法
  - 初中：感官优先三步可视化
  - 考研：考点解剖（题型/真题/得分步骤）
  - 学科方法论（method_guide）与深度阶梯（SUBJECT_GRADE_DEPTH）是否进入输出

方法：真实 POST /api/teach/stream（携带 grade_level），抓 presentation 内容，
按学段特征正则检查（结合 GRADE_SCAFFOLDS 段名）。LLM 慢（30-60s/次），
逐发间隔 + 限流窗口控制（每次后 sleep 5s，共 4 次 < 30/min 上限）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime

import requests

BASE = os.environ.get("PAEG_TEST_URL", "http://127.0.0.1:5000")
OUT = os.path.dirname(os.path.abspath(__file__))

# 学段期望特征（对应 GRADE_SCAFFOLDS 段名 + 用户需求）
CASES = [
    {
        "grade": "middle_school", "subject": "math", "concept": "什么是负数",
        "expect": {
            "感官/生活化": re.compile(r"生活|例子|比如|现象|看得见|感觉"),
            "可视化": re.compile(r"图|表|示意|画面|数轴"),
            "复述引导": re.compile(r"复述|自己的话|说说"),
        },
    },
    {
        "grade": "high_school", "subject": "math", "concept": "导数的几何意义",
        "expect": {
            "定义+公式": re.compile(r"定义|公式|导数|切线"),
            "题型方法": re.compile(r"方法|题型|步骤|套路"),
            "反例/误区": re.compile(r"误区|常见错误|反例|注意"),
        },
    },
    {
        "grade": "undergraduate", "subject": "math", "concept": "微积分基本定理",
        "expect": {
            "lecture式严格定义": re.compile(r"严格定义|定理|证明|推导|条件"),
            "高屋建瓴方法论": re.compile(r"方法论|思想|框架|本质|为什么"),
            "应用/学科视野": re.compile(r"应用|学科|历史|拓展|联系"),
        },
    },
    {
        "grade": "graduate_exam", "subject": "math", "concept": "二重积分计算",
        "expect": {
            "考点定位": re.compile(r"考点|真题|频次|必考"),
            "题型套路": re.compile(r"题型|套路|步骤|方法|变式"),
            "得分/易错": re.compile(r"踩分|得分|易错|考场"),
        },
    },
]


def probe(case: dict) -> dict:
    payload = {
        "concept": case["concept"], "subject": case["subject"],
        "learner_id": f"u_gq_{case['grade']}",
        "grade_level": case["grade"],
    }
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/api/teach/stream", json=payload,
                          timeout=150, stream=True)
        body = r.text
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "elapsed": round(time.time() - t0, 1)}
    # 汇总 presentation 内容（含 srs_reminder 过滤）
    texts = []
    for _seg in body.split("\n\n"):
        for _l in _seg.splitlines():
            if _l.startswith("data: "):
                try:
                    _d = json.loads(_l[6:])
                    if _d.get("step_type") == "presentation":
                        texts.append(str(_d.get("content") or ""))
                    elif _d.get("step_type") == "teach":
                        texts.append(str(_d.get("content") or ""))
                except Exception:
                    pass
    content = "\n".join(texts)
    result = {"ok": bool(content), "elapsed": round(time.time() - t0, 1),
              "chars": len(content), "features": {}}
    for _fname, _pat in case["expect"].items():
        result["features"][_fname] = bool(_pat.search(content))
    # 深度阶梯 / 方法论注入痕迹
    result["has_depth_ladder"] = "深度阶梯" in body or "必须出现" in body
    return result


def main():
    print("=" * 60)
    print(f"学段×学科 教学质量真实验证  {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 60)
    results = []
    for i, _c in enumerate(CASES):
        print(f"\n[{i+1}/{len(CASES)}] {_c['grade']} · {_c['subject']} · {_c['concept']}")
        _r = probe(_c)
        results.append({"case": _c, "result": _r})
        if _r.get("ok"):
            print(f"  ✔ 有输出 {_r['chars']} 字（{_r['elapsed']}s） 深度阶梯={_r['has_depth_ladder']}")
            for _f, _v in _r["features"].items():
                print(f"    {'✔' if _v else '✘'} {_f}")
        else:
            print(f"  ✘ 无输出/异常: {_r.get('error')}")
        time.sleep(6)  # 限流窗口 + LLM 冷却
    # 汇总
    _pass = sum(1 for r in results if r["result"].get("ok")
                and all(r["result"]["features"].values()))
    _report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "cases": [
            {k: v for k, v in r["case"].items() if k != "expect"} | r["result"]
            for r in results
        ],
        "all_features_pass": _pass,
        "total": len(CASES),
    }
    with open(os.path.join(OUT, "grade_quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(_report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "grade_quality_report.md"), "w", encoding="utf-8") as f:
        f.write(f"# 学段×学科 教学质量验证报告（{_report['ts']}）\n\n")
        f.write(f"- 全特征通过：{_pass}/{len(CASES)}\n\n")
        for _r in _report["cases"]:
            f.write(f"## {_r['grade']} · {_r['subject']} · {_r['concept']}（{_r.get('elapsed')}s, {_r.get('chars','?')}字）\n")
            for _f, _v in (_r.get("features") or {}).items():
                f.write(f"- {'✅' if _v else '❌'} {_f}\n")
            f.write(f"- 深度阶梯注入：{'✅' if _r.get('has_depth_ladder') else '❌'}\n\n")
    print(f"\n完成：全特征通过 {_pass}/{len(CASES)}")
    print(f"报告：{OUT}/grade_quality_report.json/.md")


if __name__ == "__main__":
    main()
