"""
library_store.py — 用户上传资料库的统一存储与读取（v0.21.4+）

规范路径：<项目根>/Library/usr_knowledge/<learner_id>/
向后兼容（读取侧）：Library/user_<learner_id>/  和  Library/user_<learner_id>/<learner_id>/

设计原则：
1. 默认存到规范路径 usr_knowledge/<uid>/（与 usr/README.md 和反馈链路语义一致）
2. 读取时统一扫描规范路径 + 两条旧路径，去重后返回
3. md/txt/pdf/docx/csv/json 都尽力解析为文本，失败返回空串而不崩溃
4. server.py /api/upload（purpose=library）通过本模块决定保存目录
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Iterable, List


# ────────────────────────────────────────────────────────────────
# 路径解析
# ────────────────────────────────────────────────────────────────

# server.py 与本模块都在 <项目根>/05_实现原型/ 下，Library 在项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LIBRARY_DIR = _PROJECT_ROOT / "Library"
CANONICAL_DIRNAME = "usr_knowledge"  # 规范子目录名


def project_root() -> Path:
    """返回项目根路径（14_教育者Agent项目/）。"""
    return _PROJECT_ROOT


def resolve_library_root(learner_id: str) -> Path:
    """返回规范路径 Library/usr_knowledge/<uid>/（Path 对象，可能不存在）。"""
    if not learner_id:
        learner_id = "anonymous"
    return LIBRARY_DIR / CANONICAL_DIRNAME / learner_id


def legacy_paths(learner_id: str) -> List[Path]:
    """返回需要兼容读取的旧路径列表（不一定存在）。"""
    if not learner_id:
        learner_id = "anonymous"
    return [
        LIBRARY_DIR / f"user_{learner_id}",
        LIBRARY_DIR / f"user_{learner_id}" / learner_id,
    ]


def upload_save_dir(learner_id: str, library_root: str = "user") -> Path:
    """决定 /api/upload（purpose=library）文件实际保存目录。

    - library_root == "usr_knowledge" → 强制规范路径
    - 其他值（含默认 "user" 或 None）→ 也走规范路径（v0.21.4 起统一）
    """
    # v0.21.4: 任何 library_root 值都保存到规范路径；读取时仍兼容旧路径
    return resolve_library_root(learner_id)


# ────────────────────────────────────────────────────────────────
# 文件枚举 / 去重
# ────────────────────────────────────────────────────────────────

def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return []
    # 仅顶层文件 + 一层子目录（防误扫到更深的旧数据）
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            yield entry
        elif entry.is_dir():
            for sub in sorted(entry.iterdir()):
                if sub.is_file() and not sub.name.startswith("."):
                    yield sub


def list_user_files(learner_id: str) -> List[Path]:
    """返回该用户资料库所有可见文件的绝对路径列表。

    扫描顺序：
      1. Library/usr_knowledge/<uid>/     (规范)
      2. Library/user_<uid>/               (旧)
      3. Library/user_<uid>/<uid>/         (旧·嵌套)

    去重：以文件 basename 为键（同一文件名只保留一份，优先取规范路径）。
    """
    roots = [resolve_library_root(learner_id)] + legacy_paths(learner_id)
    seen: dict[str, Path] = {}
    for root in roots:
        for fp in _iter_files(root):
            key = fp.name
            if key not in seen:
                seen[key] = fp
    return list(seen.values())


def dedupe_by_name(paths: Iterable[Path]) -> List[Path]:
    """按 basename 去重，保序。"""
    seen: dict[str, Path] = {}
    for p in paths:
        if p.name not in seen:
            seen[p.name] = p
    return list(seen.values())


# ────────────────────────────────────────────────────────────────
# 单文件文本提取（尽力而为，失败返回空串）
# ────────────────────────────────────────────────────────────────

_READ_LIMIT = 800  # 单文件抽取上限字符


def _read_text_file(path: Path, limit_chars: int = _READ_LIMIT) -> str:
    """尝试 UTF-8 → GBK 读文本。"""
    raw = b""
    try:
        raw = path.read_bytes()
    except Exception:
        return ""
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return raw.decode(enc, errors="ignore")[:limit_chars]
        except Exception:
            continue
    return ""


def _read_pdf(path: Path, limit_chars: int = _READ_LIMIT) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
        buf: list[str] = []
        total = 0
        for i, page in enumerate(reader.pages[:3]):  # 最多前 3 页
            if total >= limit_chars:
                break
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt:
                buf.append(txt)
                total += len(txt)
        return "\n".join(buf)[:limit_chars]
    except Exception:
        return ""


def _read_docx(path: Path, limit_chars: int = _READ_LIMIT) -> str:
    try:
        import docx  # type: ignore
    except Exception:
        return ""
    try:
        d = docx.Document(str(path))
        out: list[str] = []
        total = 0
        for para in d.paragraphs:
            if total >= limit_chars:
                break
            t = (para.text or "").strip()
            if t:
                out.append(t)
                total += len(t)
        return "\n".join(out)[:limit_chars]
    except Exception:
        return ""


def _read_csv(path: Path, limit_chars: int = _READ_LIMIT) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            buf: list[str] = []
            total = 0
            row_count = 0
            for row in reader:
                row_count += 1
                if row_count > 50:  # 最多 50 行
                    break
                line = "\t".join(row)
                if total + len(line) > limit_chars:
                    line = line[: limit_chars - total]
                buf.append(line)
                total += len(line)
                if total >= limit_chars:
                    break
            return "\n".join(buf)
    except Exception:
        return ""


def _read_json(path: Path, limit_chars: int = _READ_LIMIT) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return text[:limit_chars]
    except Exception:
        # 解析失败则按文本读
        return _read_text_file(path, limit_chars)


_TEXT_EXTRACTORS = {
    ".md": _read_text_file,
    ".txt": _read_text_file,
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".csv": _read_csv,
    ".json": _read_json,
}


def read_user_file_text(path: Path | str, limit_chars: int = _READ_LIMIT) -> str:
    """根据扩展名选对应提取器；失败返回空串。绝对不抛异常。"""
    p = Path(path) if not isinstance(path, Path) else path
    if not p.exists() or not p.is_file():
        return ""
    ext = p.suffix.lower()
    fn = _TEXT_EXTRACTORS.get(ext, _read_text_file)
    try:
        return fn(p, limit_chars)
    except Exception:
        return ""


# ────────────────────────────────────────────────────────────────
# 汇总入口（get_user_library 注入用）
# ────────────────────────────────────────────────────────────────

def read_user_corpus(
    learner_id: str,
    max_files: int = 5,
    per_file: int = 500,
) -> str:
    """读取该用户资料库的合并文本，用于注入 system prompt。

    返回格式：
      【用户上传资料(<n> 份，回答相关问题时请参考)】
      - 文件1
      - 文件2
      ...

      === 文件1 ===
      <前 per_file 字>

      === 文件2 ===
      ...
    无资料返回 ""。
    """
    files = list_user_files(learner_id)
    if not files:
        return ""
    # 只对前 max_files 个抽正文；其余仅列名
    parts: List[str] = [
        f"【用户上传资料（{len(files)} 份，回答相关问题时请参考）】"
    ]
    for fp in files:
        parts.append(f"- {fp.name}")
    parts.append("")
    for fp in files[:max_files]:
        body = read_user_file_text(fp, limit_chars=per_file).strip()
        if body:
            parts.append(f"=== {fp.name} ===")
            parts.append(body[:per_file])
            parts.append("")
    return "\n".join(parts).rstrip()


# ────────────────────────────────────────────────────────────────
# 文件元信息（给 /api/user-library 返回）
# ────────────────────────────────────────────────────────────────

def _classify(ext: str) -> str:
    ext = ext.lower()
    if ext in (".md", ".txt"):
        return "text"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext == ".csv":
        return "csv"
    if ext == ".json":
        return "json"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return "image"
    return "other"


def list_user_file_info(learner_id: str) -> List[dict]:
    """返回结构化文件列表：[{name, path, type, size, library_root}]。

    library_root 字段: "usr_knowledge" / "user_<uid>" / "user_<uid>/<uid>"
    """
    canonical_root = resolve_library_root(learner_id)
    legacy_roots = legacy_paths(learner_id)

    def _classify_root(p: Path) -> str:
        try:
            rel = p.relative_to(LIBRARY_DIR)
        except ValueError:
            return ""
        return rel.parts[0] if rel.parts else ""

    # 收集所有文件（含规范路径与旧路径中的所有条目），按 (library_root, name) 去重
    items: List[dict] = []
    seen_keys: set = set()
    for root in [canonical_root] + legacy_roots:
        if not root.exists() or not root.is_dir():
            continue
        # 该根目录的"逻辑 library_root"标签：用于去重 key
        logical_root = _classify_root(root) or root.name
        for fp in _iter_files(root):
            # 规范化路径用于去重（避免 user_<uid>/ 与 user_<uid>/<uid>/ 下重复扫到同一物理文件）
            try:
                resolved = str(fp.resolve())
            except Exception:
                resolved = str(fp)
            key = (resolved, fp.name, logical_root)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            try:
                size = fp.stat().st_size
            except Exception:
                size = 0
            items.append({
                "name": fp.name,
                "path": str(fp.relative_to(_PROJECT_ROOT)).replace("\\", "/"),
                "type": _classify(fp.suffix),
                "size": size,
                "library_root": logical_root,
            })
    return items
