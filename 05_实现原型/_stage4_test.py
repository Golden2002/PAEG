# -*- coding: utf-8 -*-
import os, sys, json, subprocess, time, urllib.request, urllib.error
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
PROJ = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:5000"
print("PROJ=", PROJ)
print("BASE=", BASE)
def run_py(args, cwd=None, timeout=90):
    if cwd is None: cwd = PROJ
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable] + list(args), cwd=cwd, env=env,
            capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "", "[TIMEOUT " + str(timeout) + "s]", time.time() - t0
    except Exception as e:
        return -2, "", "[EXC " + str(e) + "]", time.time() - t0
def http(method, path, data=None, headers=None, timeout=15):
    url = BASE + path
    body = None
    h = {"Accept": "application/json"}
    if headers: h.update(headers)
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            h["Content-Type"] = "application/json"
        else:
            body = data if isinstance(data, bytes) else data.encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), time.time() - t0
    except Exception as e:
        return 0, "[EXC " + type(e).__name__ + ": " + str(e) + "]", time.time() - t0
print("======================================================================")
print("Section 1: audit_check.py")
print("======================================================================")
sys.stdout.flush()
rc1, out1, err1, dt1 = run_py(["audit_check.py"], timeout=180)
print("rc=" + str(rc1) + "  time=" + str(round(dt1, 1)) + "s")
tail = (out1 or "")[-3500:]
print("--- stdout (tail) ---")
print(tail)
if err1 and err1.strip():
    print("--- stderr (tail) ---")
    print(err1[-1500:])
sys.stdout.flush()
print("")
print("======================================================================")
print("Section 2: pytest 3 batches")
print("======================================================================")
batches = [
    ("BATCH-A: v037+indiv+routing", ["tests/test_v037_regressions.py", "tests/test_individuality_v023.py", "tests/test_routing_v024.py"]),
    ("BATCH-B: pipeline+contracts", ["tests/test_pipeline_integrity.py", "tests/test_contracts.py"]),
    ("BATCH-C: v035 routing+recommend", ["tests/test_v035_llm_first_routing.py", "tests/test_v035_recommend_branch.py"]),
]
batch_results = []
for name, files in batches:
    print("")
    print("======================================================================")
    print("Section 2: " + name)
    print("======================================================================")
    sys.stdout.flush()
    rc_b, out_b, err_b, dt_b = run_py(["-m", "pytest"] + files + ["-q", "--no-header", "--tb=line", "-p", "no:cacheprovider", "--rootdir", PROJ], timeout=90)
    print("rc=" + str(rc_b) + "  time=" + str(round(dt_b, 1)) + "s")
    print("--- stdout (last 2500) ---")
    print((out_b or "")[-2500:])
    if "FAILED" in (out_b or "") or "ERROR" in (out_b or "") or rc_b != 0:
        print("--- stderr (last 1200) ---")
        print((err_b or "")[-1200:])
    sys.stdout.flush()
    batch_results.append((name, rc_b, dt_b))
print("")
print("======================================================================")
print("Section 3: Core Endpoints")
print("======================================================================")
sys.stdout.flush()
endpoint_table = []
st, b, dt = http("GET", "/api/health", timeout=10)
endpoint_table.append(("GET /api/health", st, b[:300], dt))
print("  /api/health          -> " + str(st) + "  (" + str(round(dt, 2)) + "s)")
concept = chr(0x4ec0) + chr(0x4e48) + chr(0x662f) + chr(0x5bfc) + chr(0x6570)
payload = {"concept": concept, "learner_id": "u3", "subject": "high_school_math", "grade_level": "high_school", "nickname": "测试生"}
st, b, dt = http("POST", "/api/teach/stream", data=payload, timeout=15)
has_pres = "presentation" in b
endpoint_table.append(("POST /api/teach/stream", st, "len=" + str(len(b)) + " has_presentation=" + str(has_pres), dt))
print("  /api/teach/stream    -> " + str(st) + "  (" + str(round(dt, 2)) + "s)  presentation=" + str(has_pres))
if st != 200:
    print("    body[:500]=" + b[:500])
sys.stdout.flush()
aff_text = chr(0x6211) + chr(0x4eca) + chr(0x5929) + chr(0x6709) + chr(0x70b9) + chr(0x7d2f)
payload2 = {"learner_id": "u3", "text": aff_text, "subject": "math"}
st, b, dt = http("POST", "/api/affection", data=payload2, timeout=10)
endpoint_table.append(("POST /api/affection", st, b[:300], dt))
print("  /api/affection       -> " + str(st) + "  (" + str(round(dt, 2)) + "s)")
tts_text = chr(0x4f60) + chr(0x597d) + chr(0x5bfc) + chr(0x6570) + chr(0x662f) + chr(0x53d8) + chr(0x5316) + chr(0x7387)
payload3 = {"text": tts_text, "voice": "default"}
st, b, dt = http("POST", "/api/voice/tts", data=payload3, timeout=10)
ok_tts = "\"ok\":true" in b or "\"ok\": true" in b
endpoint_table.append(("POST /api/voice/tts", st, "ok=" + str(ok_tts), dt))
print("  /api/voice/tts       -> " + str(st) + "  (" + str(round(dt, 2)) + "s)  ok=" + str(ok_tts))
st, b, dt = http("GET", "/api/meta-log/u3", timeout=10)
endpoint_table.append(("GET /api/meta-log/u3", st, "len=" + str(len(b)), dt))
print("  /api/meta-log/u3     -> " + str(st) + "  (" + str(round(dt, 2)) + "s)")
st, b, dt = http("POST", "/api/voice/stt", data=b"", headers={"Content-Type": "application/octet-stream"}, timeout=10)
endpoint_table.append(("POST /api/voice/stt (no audio)", st, b[:300], dt))
print("  /api/voice/stt (no)  -> " + str(st) + "  (" + str(round(dt, 2)) + "s)")
print("")
print("======================================================================")
print("Section 4: Frontend Page")
print("======================================================================")
sys.stdout.flush()
st, b, dt = http("GET", "/", timeout=10)
has_mr = "MediaRecorder" in b
has_stt = "/api/voice/stt" in b
print("  GET /            -> " + str(st) + "  (" + str(round(dt, 2)) + "s)  len=" + str(len(b)))
print("  MediaRecorder   -> " + str(has_mr))
print("  /api/voice/stt  -> " + str(has_stt))
if has_mr:
    idx = b.find("MediaRecorder")
    print("    MediaRecorder ctx: " + repr(b[max(0,idx-60):idx+250]))
if has_stt:
    idx = b.find("/api/voice/stt")
    print("    /api/voice/stt ctx: " + repr(b[max(0,idx-60):idx+250]))
sys.stdout.flush()
print("")
print("======================================================================")
print("SUMMARY")
print("======================================================================")
report = {
    "audit_check_rc": rc1,
    "audit_check_passed_text": "15/15" in (out1 or ""),
    "pytest_batches": [{"name": n, "rc": r, "time_s": t} for n, r, t in batch_results],
    "endpoints": [{"name": n, "status": s, "detail": d, "time_s": t} for n, s, d, t in endpoint_table],
    "frontend": {"status": st, "has_MediaRecorder": has_mr, "has_stt_path": has_stt},
}
report_path = r"C:\\Temp\\stage4_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("Report written: " + report_path)
