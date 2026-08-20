# -*- coding: utf-8 -*-
"""test_pptx_image_supplier.py — PPT 图片供应器单元测试（TDD ⭐ RED→GREEN）

任务背景：PAEG 生成 PPT 时为每页配 1-2 张相关图片。资源按 5 级优先级链查找：
  ① 用户资料库 Library/usr_knowledge/<uid>/（jieba 关键词匹配文件名）
  ② 公共文件夹 Library/ppt_images/ + ~/.paeg/ppt_images/
  ③ 缓存 Library/.cache/ppt_images/<md5>.json（命中即跳过网络）
  ④ 联网 Bing 图片搜索（5s 超时，HTML 解析 murl 字段）
  ⑤ 写入缓存（仅网络成功时）

测试隔离策略：
- test_local_match 按用户要求用真实路径 Library/usr_knowledge/test_uid/，
  PUBLIC_DIRS 与 CACHE_DIR 仍 monkeypatch 到 tmp_path（避免污染真实目录）。
- 其余 5 个测试全部 monkeypatch USR_KNOWLEDGE_DIR / PUBLIC_DIRS / CACHE_DIR
  到 tmp_path，形成完整 hermetic 沙盒。
- 所有测试 monkeypatch pis.requests.get 在不应触发网络时显式失败，
  防止实现 bug 静默走真实网络（拖慢测试 + 污染生产缓存）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# 项目根（D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目）
_PROJ_ROOT = Path(__file__).resolve().parents[2]
_REAL_USR_TEST_UID = _PROJ_ROOT / "Library" / "usr_knowledge" / "test_uid"


# ────────────────────────────────────────────────────────────
#  Fixtures
# ────────────────────────────────────────────────────────────
@pytest.fixture
def fake_plant_in_real_usr():
    """test_local_match 用：真实 Library/usr_knowledge/test_uid/植物_光合.png。

    用户明确要求把假图放在 Library/usr_knowledge/test_uid/，测试结束后清理。
    """
    _REAL_USR_TEST_UID.mkdir(parents=True, exist_ok=True)
    plant = _REAL_USR_TEST_UID / "植物_光合.png"
    # 最小 PNG 头（8 magic bytes）+ 填充（足够 _download_image 头校验通过）
    plant.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    try:
        yield plant
    finally:
        try:
            plant.unlink()
        except OSError:
            pass


@pytest.fixture
def isolated_pis(monkeypatch, tmp_path):
    """hermetic 沙盒：把模块 3 个路径常量全重定向到 tmp_path。

    返回 (pis_mod, usr_root, public_dir, cache_dir)：
    - usr_root = tmp_path/usr_knowledge（无任何 test_uid/ 子目录 → local miss）
    - public_dir = tmp_path/public（测试按需写入图片）
    - cache_dir = tmp_path/cache（测试按需预置缓存）
    """
    import pptx_image_supplier as pis

    usr = tmp_path / "usr_knowledge"
    public = tmp_path / "public"
    cache = tmp_path / "cache"
    usr.mkdir(parents=True)
    public.mkdir(parents=True)
    cache.mkdir(parents=True)

    monkeypatch.setattr(pis, "USR_KNOWLEDGE_DIR", usr)
    monkeypatch.setattr(pis, "PUBLIC_DIRS", [public])
    monkeypatch.setattr(pis, "CACHE_DIR", cache)
    return pis, usr, public, cache


def _block_network(monkeypatch, pis):
    """monkeypatch pis.requests.get 抛异常；网络被意外调用时立即暴露 bug。"""

    def _boom(*a, **k):
        raise AssertionError("网络不应被调用（应在前置步骤命中）")

    monkeypatch.setattr(pis.requests, "get", _boom)


# ────────────────────────────────────────────────────────────
#  测试 1：用户资料库本地命中
# ────────────────────────────────────────────────────────────
def test_local_match(fake_plant_in_real_usr, monkeypatch, tmp_path):
    """真实 Library/usr_knowledge/test_uid/植物_光合.png 应被 jieba 关键词匹配命中。"""
    import pptx_image_supplier as pis

    # PUBLIC_DIRS 与 CACHE_DIR 仍 monkeypatch 到 tmp（避免污染真实目录）
    pub = tmp_path / "public"
    pub.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(pis, "PUBLIC_DIRS", [pub])
    monkeypatch.setattr(pis, "CACHE_DIR", cache)
    _block_network(monkeypatch, pis)

    result = pis.find_images_for_slide(
        "植物光合作用", ["叶绿体"], uid="test_uid", max_results=2
    )

    assert isinstance(result, list)
    assert any("植物_光合" in p for p in result), (
        f"期望命中真实路径下的 植物_光合.png，实际：{result}"
    )


# ────────────────────────────────────────────────────────────
#  测试 2：local miss → 扫 PUBLIC_DIRS
# ────────────────────────────────────────────────────────────
def test_local_miss_falls_to_public(isolated_pis, monkeypatch):
    """usr 无匹配 → 扫 PUBLIC_DIRS（命中即返回，不触发网络）。"""
    pis, usr, public, cache = isolated_pis

    # public 放一张文件名命中关键词的图
    pub_img = public / "植物_叶绿体.png"
    pub_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    _block_network(monkeypatch, pis)

    result = pis.find_images_for_slide(
        "植物光合作用", ["叶绿体"], uid="test_uid_none"
    )

    assert any("植物_叶绿体" in p for p in result), (
        f"期望命中 public 里的 植物_叶绿体.png，实际：{result}"
    )


# ────────────────────────────────────────────────────────────
#  测试 3：网络异常 → 静默返回 []
# ────────────────────────────────────────────────────────────
def test_network_failure_silent(isolated_pis, monkeypatch):
    """Bing 接口异常时，返回 [] 而不向上抛异常。"""
    pis, usr, public, cache = isolated_pis

    def _boom(*a, **k):
        raise ConnectionError("simulated Bing outage")

    monkeypatch.setattr(pis.requests, "get", _boom)

    # 不抛异常，且返回 []
    result = pis.find_images_for_slide("随便", ["任意"], uid="test_uid")

    assert result == [], f"网络失败应返回 []，实际：{result}"


# ────────────────────────────────────────────────────────────
#  测试 4：缓存命中不联网
# ────────────────────────────────────────────────────────────
def test_cache_hit(isolated_pis, monkeypatch):
    """预置 cache 文件 → 命中即返回，不触发网络。"""
    pis, usr, public, cache = isolated_pis

    _block_network(monkeypatch, pis)

    # 计算 cache key 并预置文件
    key = pis._cache_key("植物光合作用", ["叶绿体"], "test_uid")
    cached_urls = [
        "https://example.com/img1.jpg",
        "https://example.com/img2.jpg",
    ]
    (cache / f"{key}.json").write_text(
        json.dumps({"urls": cached_urls}), encoding="utf-8"
    )

    result = pis.find_images_for_slide(
        "植物光合作用", ["叶绿体"], uid="test_uid"
    )

    assert result == cached_urls, (
        f"cache 命中应原样返回 urls，实际：{result}"
    )


# ────────────────────────────────────────────────────────────
#  测试 5：空输入短路
# ────────────────────────────────────────────────────────────
def test_empty_inputs(isolated_pis, monkeypatch):
    """title 与 points 都空（或其一空）→ 立即返回 []，不查任何源。"""
    pis, usr, public, cache = isolated_pis

    _block_network(monkeypatch, pis)

    assert pis.find_images_for_slide("", [], uid="test_uid") == []
    assert pis.find_images_for_slide("", ["a"], uid="test_uid") == []
    assert pis.find_images_for_slide("标题", [], uid="test_uid") == []
    assert pis.find_images_for_slide(None, None, uid="test_uid") == []


# ────────────────────────────────────────────────────────────
#  测试 6：max_results cap
# ────────────────────────────────────────────────────────────
def test_max_results_cap(isolated_pis, monkeypatch):
    """5 个候选 URL → 仅返回 max_results=2 个。"""
    pis, usr, public, cache = isolated_pis

    _block_network(monkeypatch, pis)

    key = pis._cache_key("植物光合作用", ["叶绿体"], "test_uid")
    five = [f"https://example.com/img{i}.jpg" for i in range(5)]
    (cache / f"{key}.json").write_text(
        json.dumps({"urls": five}), encoding="utf-8"
    )

    result = pis.find_images_for_slide(
        "植物光合作用", ["叶绿体"], uid="test_uid", max_results=2
    )

    assert len(result) == 2, f"应截断到 2，实际：{len(result)}"
    assert result == five[:2], f"应返回前 2 个 URL，实际：{result}"