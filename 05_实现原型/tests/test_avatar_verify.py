"""Flask test_client 验证 /api/avatar v0.36 修复。"""
import io
import os
import sys
import glob

sys.path.insert(0, r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型')
os.chdir(r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型')

from server import app

app.config['TESTING'] = True
client = app.test_client()

# 清理目标测试用户旧头像
for p in glob.glob(r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型\uploads\avatar\avatar_tester_*'):
    try: os.remove(p)
    except Exception: pass

UPLOAD_DIR = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型\uploads\avatar'

print("=== Case 1: 合法 png 上传 ===")
png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
r = client.post('/api/avatar', data={
    'avatar': (io.BytesIO(png_data), 'test.png'),
    'learner_id': 'tester',
}, content_type='multipart/form-data')
print(f"  status={r.status_code}, body={r.get_json()}")
assert r.status_code == 200, f"expected 200, got {r.status_code}"
body = r.get_json()
assert body['ok'] is True
assert body['url'].startswith('/uploads/avatar/avatar_tester')
assert body['url'].endswith('.png')
print("  [OK] url 格式正确")

saved = os.path.join(UPLOAD_DIR, 'avatar_tester.png')
assert os.path.exists(saved), f"file not saved: {saved}"
print(f"  [OK] 文件已落盘 ({os.path.getsize(saved)} bytes)")

print("\n=== Case 2: 静态服务 /uploads/avatar/avatar_tester.png ===")
r = client.get('/uploads/avatar/avatar_tester.png')
print(f"  status={r.status_code}, content-type={r.headers.get('Content-Type')}")
assert r.status_code == 200
print(f"  [OK] 静态服务可达")

print("\n=== Case 3: 非法扩展名 .exe -> 400 + ok:False ===")
exe_data = b'MZ\x90\x00' + b'\x00' * 100
r = client.post('/api/avatar', data={
    'avatar': (io.BytesIO(exe_data), 'evil.exe'),
    'learner_id': 'tester',
}, content_type='multipart/form-data')
print(f"  status={r.status_code}, body={r.get_json()}")
assert r.status_code == 400
body = r.get_json()
assert body.get('ok') is False, f"v0.36 应返回 ok:False, 实际 {body}"
assert 'error' in body
print(f"  [OK] 拒绝 .exe, error={body['error']!r}")

print("\n=== Case 4: 路径穿越 learner_id='../etc' ===")
r = client.post('/api/avatar', data={
    'avatar': (io.BytesIO(png_data), 'x.png'),
    'learner_id': '../etc',
}, content_type='multipart/form-data')
print(f"  status={r.status_code}, body={r.get_json()}")
assert r.status_code == 400
body = r.get_json()
assert body.get('ok') is False
print(f"  [OK] 拒绝路径穿越")

print("\n=== Case 5: 无文件 ===")
r = client.post('/api/avatar', data={'learner_id': 'tester'}, content_type='multipart/form-data')
print(f"  status={r.status_code}, body={r.get_json()}")
assert r.status_code == 400
body = r.get_json()
assert body.get('ok') is False
print(f"  [OK] 拒绝空文件")

print("\n=== Case 6: 换 .jpg 应覆盖旧 png ===")
jpg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
r = client.post('/api/avatar', data={
    'avatar': (io.BytesIO(jpg_data), 'test.jpg'),
    'learner_id': 'tester',
}, content_type='multipart/form-data')
print(f"  status={r.status_code}, body={r.get_json()}")
assert r.status_code == 200
old_png = os.path.join(UPLOAD_DIR, 'avatar_tester.png')
new_jpg = os.path.join(UPLOAD_DIR, 'avatar_tester.jpg')
assert not os.path.exists(old_png), "旧 png 应被清理"
assert os.path.exists(new_jpg), "新 jpg 应存在"
print(f"  [OK] 覆盖式保存 + 旧扩展清理")

print("\n=== Case 7: 新 jpg 可访问 ===")
r = client.get('/uploads/avatar/avatar_tester.jpg')
print(f"  status={r.status_code}, bytes={len(r.data)}")
assert r.status_code == 200
print(f"  [OK] jpg 可访问")

print("\n=== 全部验证通过 ===")

# 清理
for p in glob.glob(os.path.join(UPLOAD_DIR, 'avatar_tester_*')):
    try: os.remove(p)
    except Exception: pass