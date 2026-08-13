# -*- coding: utf-8 -*-
"""PAEG 测试基础设施（Oracle 标准 v1）
Layer 1: API 级测试（快，先跑）
Layer 2: Playwright UI 集成测试（后跑）
"""
import os
import sys

BASE = r'D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型'
EVIDENCE = os.path.join(os.path.dirname(__file__), '..', '..', 'evidence')
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import json
import time
import urllib.request
from datetime import datetime


class ApiClient:
    """轻量 API 测试客户端（不经 Flask test_client，走真实 HTTP）。"""

    def __init__(self, base: str = 'http://localhost:5000'):
        self.base = base

    def post(self, path: str, data: dict, timeout: int = 60) -> dict:
        """POST JSON，返回 {status, body, ttfb_ms}。"""
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            self.base + path, data=body,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST')
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                ttfb = (time.time() - t0) * 1000
                try:
                    return {'status': resp.status, 'body': json.loads(raw),
                            'ttfb_ms': round(ttfb, 1)}
                except Exception:
                    return {'status': resp.status, 'body_raw': raw,
                            'ttfb_ms': round(ttfb, 1)}
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', errors='replace')
            return {'status': e.code, 'body_raw': raw,
                    'ttfb_ms': round((time.time() - t0) * 1000, 1)}
        except Exception as e:
            return {'status': 0, 'error': str(e),
                    'ttfb_ms': round((time.time() - t0) * 1000, 1)}

    def get(self, path: str, timeout: int = 30) -> dict:
        t0 = time.time()
        try:
            with urllib.request.urlopen(self.base + path, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                return {'status': resp.status, 'body': raw,
                        'ttfb_ms': round((time.time() - t0) * 1000, 1)}
        except Exception as e:
            return {'status': 0, 'error': str(e),
                    'ttfb_ms': round((time.time() - t0) * 1000, 1)}


def save_evidence(test_id: str, result: dict):
    """证据落盘。"""
    os.makedirs(EVIDENCE, exist_ok=True)
    fp = os.path.join(EVIDENCE, f'{test_id}_{datetime.now().strftime("%H%M%S")}.json')
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return fp
