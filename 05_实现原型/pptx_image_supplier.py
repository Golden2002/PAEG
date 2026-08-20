# -*- coding: utf-8 -*-
"""PPT 图片供应器（v1.0 ⭐）

5 级优先级链（永不阻塞，每步 try/except）：
  ① 用户资料库  Library/usr_knowledge/<uid>/     —— jieba 关键词匹配文件名
  ② 公共文件夹   Library/ppt_images/ + ~/.paeg/ppt_images/
  ③ 缓存检查     Library/.cache/ppt_images/<md5>.json（命中即跳过网络）
  ④ 联网搜索     Bing 图片搜索（免 key，5s 超时，HTML 解析 murl 字段）
  ⑤ 写入缓存     仅网络成功时落盘（避免重复联网）

约束：
- 永不阻塞：所有外部调用（requests、文件 IO）都用 try/except 包裹，
  失败静默返回 []。上层（PPT 生成器）拿到 [] 降级为无图 PPT。
- 返回类型：list[str]，本地命中 = 绝对文件路径；网络命中 = 图片直链 URL。
- max_results 同时约束本地匹配数、缓存返回数、网络结果数。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import List, Sequence

import jieba
import requests

# ────────────────────────────────────────────────────────────
# 路径常量（monkeypatch 友好 —— 测试重定向到 tmp_path）
# ────────────────────────────────────────────────────────────
_PROJ = Path(__file__).resolve().parents[1]
USR_KNOWLEDGE_DIR: Path = _PROJ / "Library" / "usr_knowledge"
PUBLIC_DIRS: List[Path] = [
    _PROJ / "Library" / "ppt_images",
    Path.home() / ".paeg" / "ppt_images",
]
CACHE_DIR: Path = _PROJ / "Library" / ".cache" / "ppt_images"

# ────────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────────
MAX_RESULTS_DEFAULT = 2
NETWORK_TIMEOUT = 5          # Bing 联网搜索硬超时（秒）
DOWNLOAD_TIMEOUT = 8         # _download_image 超时（秒）
MAX_IMG_SIZE = 5 * 1024 * 1024  # 5MB —— 超大图直接放弃
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# jieba 停用词（短语层）
_JIEBA_STOP = frozenset({
    "什么", "如何", "怎样", "为什么", "哪些", "这里", "那里", "这个", "那个",
    "一下", "一种", "一些", "我们", "你们", "他们", "以及", "或者",
})

# jieba dict 预热（避免首个测试 ~1s 延迟）
try:
    jieba.lcut("初始化")
except Exception:
    pass


# ────────────────────────────────────────────────────────────
# 关键词 & 路径工具
# ────────────────────────────────────────────────────────────
def _cache_key(title: str, points: Sequence[str], uid: str) -> str:
    """cache 文件名 = md5(title + '|' + '|'.join(points) + '|' + uid)。"""
    s = f"{title}|{'|'.join(points or [])}|{uid}"
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _extract_keywords(text: str, max_n: int = 5) -> List[str]:
    """jieba 切词 → 2-8 字关键词 → 去停用词 → 最多 max_n 个（保序去重）。"""
    if not text:
        return []
    try:
        toks = [w.strip() for w in jieba.lcut(text) if w.strip()]
    except Exception:
        return []
    out: List[str] = []
    seen: set = set()
    for t in toks:
        if len(t) < 2 or len(t) > 8:
            continue
        if t in _JIEBA_STOP or t in seen:
            continue
        if re.fullmatch(r"[\W\d_]+", t):
            continue
        out.append(t)
        seen.add(t)
        if len(out) >= max_n:
            break
    return out


def _match_score(name: str, keywords: List[str]) -> int:
    """文件名命中关键词的个数（0 = 不匹配）。"""
    if not keywords:
        return 0
    n = name.lower()
    return sum(1 for kw in keywords if kw.lower() in n)


def _scan_dir_for_matches(d: Path, keywords: List[str], max_n: int) -> List[str]:
    """扫一个目录，关键词匹配文件名，按命中数降序，返回绝对路径列表。"""
    if not d or not d.is_dir() or not keywords:
        return []
    try:
        cands: List[tuple] = []
        for p in d.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in IMAGE_EXTS:
                continue
            score = _match_score(p.name, keywords)
            if score > 0:
                cands.append((score, str(p)))
        cands.sort(key=lambda x: (-x[0], x[1]))  # 命中数降序，文件名次之稳定排序
        return [path for _, path in cands[:max_n]]
    except Exception:
        return []


# ────────────────────────────────────────────────────────────
# 缓存读写（静默失败）
# ────────────────────────────────────────────────────────────
def _read_cache(title: str, points: Sequence[str], uid: str) -> List[str]:
    """命中缓存返回 URL 列表；miss / 文件损坏 / IO 失败 → []。"""
    try:
        fp = CACHE_DIR / f"{_cache_key(title, points, uid)}.json"
        if not fp.is_file():
            return []
        data = json.loads(fp.read_text(encoding="utf-8"))
        urls = data.get("urls") if isinstance(data, dict) else []
        return [u for u in (urls or []) if isinstance(u, str) and u]
    except Exception:
        return []


def _write_cache(title: str, points: Sequence[str], uid: str,
                 urls: List[str]) -> None:
    """网络成功时写入缓存（静默失败）。"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fp = CACHE_DIR / f"{_cache_key(title, points, uid)}.json"
        fp.write_text(
            json.dumps({"urls": urls[:MAX_RESULTS_DEFAULT]}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# 联网搜索（Bing 图片）
# ────────────────────────────────────────────────────────────
def _bing_image_search(query: str, max_results: int = MAX_RESULTS_DEFAULT) -> List[str]:
    """Bing 图片搜索：HTML 解析 murl 字段，5s 超时，免 key。"""
    if not query or not query.strip():
        return []
    try:
        r = requests.get(
            "https://www.bing.com/images/search",
            params={"q": query, "first": "1",
                    "count": str(max(10, max_results * 4)),
                    "qft": "+filterui:photo-photo"},
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=NETWORK_TIMEOUT,
        )
        r.raise_for_status()
        html = r.text
    except Exception:
        return []
    # murl = 图片直链（Bing 在 HTML 里以 JSON 字符串嵌入）
    urls: List[str] = []
    seen: set = set()
    for m in re.finditer(r'"murl"\s*:\s*"([^"]+)"', html):
        u = m.group(1).replace("\\u002f", "/").replace("\\/", "/")
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u)
            urls.append(u)
        if len(urls) >= max_results:
            break
    # 兜底：若 murl 一个都没抓到，从 <img src="...jpg|png|gif"> 抓
    if not urls:
        for m in re.finditer(
            r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif))"', html, re.I
        ):
            u = m.group(1)
            if u.startswith(("http://", "https://")) and u not in seen:
                seen.add(u)
                urls.append(u)
            if len(urls) >= max_results:
                break
    return urls


# ────────────────────────────────────────────────────────────
# 图片下载与校验（独立函数，供上层按需调用）
# ────────────────────────────────────────────────────────────
def _download_image(url: str, dest: Path,
                    timeout: int = DOWNLOAD_TIMEOUT) -> bool:
    """requests stream 下载 → 校验图片头（PNG/JPG/GIF/RIFF）→ >5MB 放弃。

    返回 True = 已落盘；False = 任何一步失败（url 不可达 / 头不对 / 超大）。
    """
    try:
        with requests.get(url, stream=True, timeout=timeout,
                          headers={"User-Agent": _UA}) as r:
            r.raise_for_status()
            # Content-Length 预检
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > MAX_IMG_SIZE:
                return False
            written = 0
            chunks: List[bytes] = []
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_IMG_SIZE:
                    return False
                chunks.append(chunk)
            if written < 16:
                return False
            data = b"".join(chunks)
            head = data[:16]
            if not (head.startswith(b"\x89PNG\r\n\x1a\n") or  # PNG
                    head.startswith(b"\xff\xd8\xff") or        # JPEG
                    head.startswith(b"GIF8") or                 # GIF87a/GIF89a
                    head[:4] == b"RIFF"):                       # WebP
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return True
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
# 公共入口（5 级优先级链）
# ────────────────────────────────────────────────────────────
def find_images_for_slide(title: str, points: Sequence[str], uid: str = "",
                          max_results: int = MAX_RESULTS_DEFAULT) -> List[str]:
    """为单页幻灯片找匹配的图（按优先级链降级）。返回 list[str]。

    - 本地命中：绝对文件路径
    - 缓存命中 / 网络命中：图片直链 URL

    永不抛异常；失败返回 []。
    """
    # 0. 参数规范化 + 空输入短路
    if points is None:
        points = []
    if not isinstance(points, (list, tuple)):
        try:
            points = list(points)
        except Exception:
            points = []
    if not title and not points:
        return []
    max_results = max(1, int(max_results or MAX_RESULTS_DEFAULT))

    keywords = _extract_keywords(f"{title} {' '.join(points)}".strip())

    # ① 用户资料库
    if uid and keywords:
        try:
            hits = _scan_dir_for_matches(USR_KNOWLEDGE_DIR / uid,
                                         keywords, max_results)
            if hits:
                return hits
        except Exception:
            pass

    # ② 公共文件夹（按 PUBLIC_DIRS 顺序，取第一个有命中的）
    if keywords:
        for d in PUBLIC_DIRS:
            try:
                hits = _scan_dir_for_matches(d, keywords, max_results)
                if hits:
                    return hits
            except Exception:
                continue

    # ③ 缓存检查（仅用于网络查询结果，命中即跳过网络）
    cached = _read_cache(title, points, uid)
    if cached:
        return cached[:max_results]

    # ④ 联网搜索（Bing 图片）
    query = f"{title} {' '.join(points)}".strip()
    if not query:
        return []
    urls = _bing_image_search(query, max_results)
    if not urls:
        return []

    # ⑤ 写缓存（仅网络成功时）
    _write_cache(title, points, uid, urls)
    return urls[:max_results]


if __name__ == "__main__":
    # 简易 CLI：python pptx_image_supplier.py 标题 [|要点1|要点2] [uid]
    import sys
    title = sys.argv[1] if len(sys.argv) > 1 else "光合作用"
    points = sys.argv[2].split("|") if len(sys.argv) > 2 else ["叶绿体"]
    uid = sys.argv[3] if len(sys.argv) > 3 else ""
    print(find_images_for_slide(title, points, uid=uid))