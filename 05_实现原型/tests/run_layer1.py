# -*- coding: utf-8 -*-
"""Layer 1: API 级快速测试（Oracle 标准 F1-F12 判据）
先跑这层——失败则不进入 UI 测试。
"""
import sys
import os
sys.path.insert(0, r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型\tests')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ui_harness import ApiClient, save_evidence

client = ApiClient()
results = []


def check(test_id, name, cond, detail=''):
    results.append({'test_id': test_id, 'name': name, 'pass': bool(cond), 'detail': detail[:200]})
    print('[%s] %s %s' % ('PASS' if cond else 'FAIL', test_id, name) + (f' | {detail[:100]}' if detail and not cond else ''))


# ── F1 教学模式：API 可达性 + 响应 ──
r = client.post('/api/teach', {'concept': '极限', 'subject': 'math',
                               'grade_level': 'high_school', 'learner_id': 'api_test'}, timeout=30)
check('f1_teach', '教学端点 200', r.get('status') == 200, str(r.get('status')))
if r.get('status') == 200 and isinstance(r.get('body'), dict):
    content = str(r.get('body', {}).get('presentation') or r.get('body', {}).get('content') or '')
    check('f1_teach_content', '教学有内容', len(content) > 50, f'{len(content)}字')

# ── F3 找答案 ──
r = client.post('/api/answer', {'question': '什么是极限？', 'subject': 'math',
                                'learner_id': 'api_test'}, timeout=30)
check('f3_answer', '找答案端点 200', r.get('status') == 200, str(r.get('status')))
if r.get('status') == 200:
    ans = str(r.get('body', {}).get('answer') or r.get('body', {}).get('content') or '')
    check('f3_answer_content', '找答案有内容', len(ans) > 30, f'{len(ans)}字')

# ── F4 学习方法 ──
r = client.post('/api/method', {'concept': '数学', 'learner_id': 'api_test'}, timeout=40)
check('f4_method', '学习方法端点 200', r.get('status') == 200, str(r.get('status')))

# ── F5 知识库 ──
r = client.post('/api/knowledge', {'concept': '极限', 'learner_id': 'api_test'}, timeout=30)
check('f5_kb', '知识库端点 200', r.get('status') == 200, str(r.get('status')))

# ── F6 倾诉 ──
r = client.post('/api/affection', {'text': '我最近压力好大，有点崩溃', 'learner_id': 'api_test'}, timeout=30)
check('f6_affection', '倾诉端点 200', r.get('status') == 200, str(r.get('status')))

# ── F12 资料推荐 / 检索 ──
r = client.post('/api/resources', {'learner_id': 'api_test', 'question': '极限的几何意义',
                                   'subject': 'math', 'grade_level': 'high_school'}, timeout=30)
check('f12_resources', '资料推荐端点 200', r.get('status') == 200, str(r.get('status')))
if r.get('status') == 200:
    sources = r.get('body', {}).get('sources') or []
    check('f12_sources', '资料有来源', len(sources) > 0 or 'ppt_outline' in r.get('body', {}), f'{len(sources)}条')

# ── F12 健康检查 ──
check('f12_health', '健康检查 200', client.get('/api/health').get('status') == 200)

# 汇总
passed = sum(1 for x in results if x['pass'])
total = len(results)
print(f'\n=== Layer1 汇总: {passed}/{total} 通过 ===')
if passed < total:
    print('失败项:')
    for x in results:
        if not x['pass']:
            print('  -', x['test_id'], x['detail'])
save_evidence('layer1_api', {'passed': passed, 'total': total, 'results': results})
