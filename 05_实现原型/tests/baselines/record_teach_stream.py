"""录制 teach_stream 基线字节流（v0.49 SSE 重构前必须跑一次）。

用途：SSE 重构（P0-P4）后，用本脚本重录，与 raw_streams/ 下旧基线对比，
保证重构前后事件顺序/字段名/必含字段完全一致（行为字节级不变）。

注意：本脚本会走真实 teach_stream 管线（含 LLM 调用），可能较慢。
      若 DEEPSEEK_API_KEY 未配置，请求会失败——此时仅用于确认端点可达性。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server import app  # noqa: E402

CASES = [
    ("entropy_highschool", "什么是熵", "physics", "high_school"),
    ("function_middleschool", "什么是二次函数", "math", "middle_school"),
    ("phenomenology_undergrad", "什么是现象学", "philosophy", "undergraduate"),
    ("weather_middleschool", "为什么会有台风", "atmospheric_science", "middle_school"),
    ("linguistics_undergrad", "什么是言语行为理论", "linguistics", "undergraduate"),
]

client = app.test_client()
out_dir = os.path.join(os.path.dirname(__file__), "raw_streams")
os.makedirs(out_dir, exist_ok=True)

for uid_suffix, concept, subject, grade in CASES:
    uid = f"baseline_{uid_suffix}_{int(time.time() * 1000)}"
    try:
        resp = client.post("/api/teach/stream", json={
            "concept": concept,
            "subject": subject,
            "grade_level": grade,
            "learner_id": uid,
        })
        raw = resp.get_data(as_text=True)
    except Exception as e:  # noqa: BLE001
        print(f"[baseline] {uid_suffix}: 请求异常 {e}")
        continue
    fp = os.path.join(out_dir, f"{uid_suffix}.sse")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"[baseline] {uid_suffix}: {len(raw)} chars -> {fp}")

print("[done] 基线录制完成。比较命令：")
print('  python -c "import difflib; a=open(r\'tests/baselines/raw_streams/a.sse\',encoding=\'utf-8\').read(); b=open(r\'tests/baselines/raw_streams/a.sse\',encoding=\'utf-8\').read(); print(list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=\'\'))[:50])"')
